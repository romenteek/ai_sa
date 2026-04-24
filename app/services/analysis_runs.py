from collections.abc import Iterable
from uuid import UUID

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.analysis_run import AnalysisRun
from app.models.clarification_round import ClarificationRound
from app.models.document import Document
from app.models.generated_task import GeneratedTask
from app.models.project import Project
from app.schemas.analysis import (
    AnalysisOutput,
    ClarificationAnswerRequest,
    ClarificationRoundResponse,
    InitialAnalysisOutput,
    AnalysisRunCreateRequest,
    AnalysisRunListItem,
    AnalysisRunReviewUpdateRequest,
    AnalysisRunResponse,
    GeneratedTaskPayload,
    SourceReference,
)
from app.services.language import LanguageCode, detect_language, has_any
from app.services.retrieval import RetrievalService, RetrievedChunk


TASK_SECTION_NAMES = (
    "backend_tasks",
    "frontend_tasks",
    "integration_tasks",
    "db_changes",
    "qa_tasks",
    "observability_tasks",
)
REVIEW_STATUSES = ("draft", "reviewed", "approved", "rejected")
NEEDS_MORE_INFO_MARKERS = ("unknown", "tbd", "not sure", "unclear", "later")
RU_NEEDS_MORE_INFO_MARKERS = ("неизвестно", "позже", "неясно", "уточнить", "пока не")


class AnalysisRunService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.retrieval = RetrievalService(db)

    def create_run(self, payload: AnalysisRunCreateRequest) -> AnalysisRunResponse:
        project = self.db.get(Project, payload.project_id)
        if project is None:
            raise ValueError("Selected project was not found.")
        requested_documents = self._load_documents(payload.document_ids)
        retrieved_chunks = self.retrieval.search_chunks(
            query=payload.query,
            document_ids=payload.document_ids,
            document_kind=payload.document_kind,
            metadata_filters=payload.metadata_filters,
            limit=payload.max_chunks,
        )
        language = payload.language or self._detect_payload_language(
            payload=payload,
            documents=requested_documents,
            retrieved_chunks=retrieved_chunks,
        )
        payload.language = language
        clarification = self._build_initial_analysis(
            payload=payload,
            project=project,
            documents=requested_documents,
            retrieved_chunks=retrieved_chunks,
            prior_answers=[],
            language=language,
        )
        validation_notes = self._build_validation_notes(payload, requested_documents, retrieved_chunks)
        is_ready = self._is_ready_for_final_analysis(clarification, prior_answers=[])
        output = (
            self._build_output(payload=payload, documents=requested_documents, retrieved_chunks=retrieved_chunks)
            if is_ready
            else self._placeholder_output(clarification)
        )

        run = AnalysisRun(
            document_id=payload.document_ids[0] if payload.document_ids else None,
            project_id=payload.project_id,
            task_type=payload.task_type,
            input_type=payload.input_type,
            input_text=payload.input_text.strip(),
            input_file_reference=payload.input_file_reference,
            status="completed" if is_ready else "needs_clarification",
            review_status="draft",
            reviewer_note="",
            request_payload=payload.model_dump(mode="json"),
            output_payload=output.model_dump(mode="json"),
            clarification_payload=clarification.model_dump(mode="json"),
            validation_notes=validation_notes,
        )
        if is_ready:
            run.generated_tasks = self._build_generated_task_rows(output)
        else:
            run.clarification_rounds = [
                ClarificationRound(
                    round_index=1,
                    questions=clarification.clarifying_questions,
                    answers="",
                )
            ]

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return self._to_response(run)

    def get_run(self, analysis_run_id: UUID) -> AnalysisRunResponse | None:
        statement = (
            select(AnalysisRun)
            .options(
                selectinload(AnalysisRun.generated_tasks),
                selectinload(AnalysisRun.project),
                selectinload(AnalysisRun.clarification_rounds),
            )
            .where(AnalysisRun.id == analysis_run_id)
        )
        run = self.db.scalars(statement).first()
        if run is None:
            return None
        return self._to_response(run)

    def list_runs(self) -> list[AnalysisRunListItem]:
        statement = select(AnalysisRun).options(selectinload(AnalysisRun.project)).order_by(AnalysisRun.created_at.desc())
        runs = self.db.scalars(statement).all()
        items: list[AnalysisRunListItem] = []
        for run in runs:
            output = AnalysisOutput.model_validate(run.output_payload or {})
            items.append(
                AnalysisRunListItem(
                    id=run.id,
                    status=run.status,
                    project_id=run.project_id,
                    project_name=run.project.name if run.project else None,
                    task_type=run.task_type,
                    review_status=run.review_status,
                    reviewer_note=run.reviewer_note or "",
                    document_id=run.document_id,
                    feature_summary=output.feature_summary,
                    confidence=output.confidence,
                    created_at=run.created_at,
                )
            )
        return items

    def list_results(self) -> list[AnalysisRunListItem]:
        return [run for run in self.list_runs() if run.status == "completed"]

    def answer_clarification(
        self,
        analysis_run_id: UUID,
        payload: ClarificationAnswerRequest,
    ) -> AnalysisRunResponse | None:
        statement = (
            select(AnalysisRun)
            .options(
                selectinload(AnalysisRun.generated_tasks),
                selectinload(AnalysisRun.project),
                selectinload(AnalysisRun.clarification_rounds),
            )
            .where(AnalysisRun.id == analysis_run_id)
        )
        run = self.db.scalars(statement).first()
        if run is None:
            return None
        if run.status == "completed":
            raise ValueError("Completed analysis results cannot accept clarification answers.")

        pending_round = next((round_ for round_ in run.clarification_rounds if not round_.answers), None)
        if pending_round is None:
            raise ValueError("No pending clarification round is available.")

        pending_round.answers = payload.answers.strip()
        pending_round.answered_at = datetime.now(UTC)
        run.status = "clarification_answered"

        create_payload = AnalysisRunCreateRequest.model_validate(run.request_payload)
        documents = self._load_documents(create_payload.document_ids)
        retrieved_chunks = self.retrieval.search_chunks(
            query=create_payload.query,
            document_ids=create_payload.document_ids,
            document_kind=create_payload.document_kind,
            metadata_filters=create_payload.metadata_filters,
            limit=create_payload.max_chunks,
        )
        prior_answers = [round_.answers for round_ in run.clarification_rounds if round_.answers]
        language = create_payload.language or self._detect_payload_language(
            payload=create_payload,
            documents=documents,
            retrieved_chunks=retrieved_chunks,
            prior_answers=prior_answers,
        )
        create_payload.language = language
        clarification = self._build_initial_analysis(
            payload=create_payload,
            project=run.project,
            documents=documents,
            retrieved_chunks=retrieved_chunks,
            prior_answers=prior_answers,
            language=language,
        )
        run.clarification_payload = clarification.model_dump(mode="json")

        if self._is_ready_for_final_analysis(clarification, prior_answers=prior_answers):
            output = self._build_output(payload=create_payload, documents=documents, retrieved_chunks=retrieved_chunks)
            run.status = "completed"
            run.output_payload = output.model_dump(mode="json")
            run.generated_tasks = self._build_generated_task_rows(output)
        else:
            run.status = "needs_clarification"
            run.clarification_rounds.append(
                ClarificationRound(
                    round_index=len(run.clarification_rounds) + 1,
                    questions=clarification.clarifying_questions,
                    answers="",
                )
            )

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return self.get_run(run.id)

    def update_review(
        self,
        analysis_run_id: UUID,
        payload: AnalysisRunReviewUpdateRequest,
    ) -> AnalysisRunResponse | None:
        run = self.db.get(AnalysisRun, analysis_run_id)
        if run is None:
            return None

        if payload.review_status not in REVIEW_STATUSES:
            raise ValueError(f"Unsupported review status: {payload.review_status}")

        run.review_status = payload.review_status
        run.reviewer_note = payload.reviewer_note.strip()
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return self._to_response(run)

    def _build_initial_analysis(
        self,
        *,
        payload: AnalysisRunCreateRequest,
        project: Project | None,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
        prior_answers: list[str],
        language: LanguageCode,
    ) -> InitialAnalysisOutput:
        missing_information: list[str] = []
        questions: list[str] = []
        assumptions = self._localized_list(
            language,
            en=[
                "Project repository/archive content is registered but not cloned or indexed in this milestone.",
                "Existing uploaded documents remain the only retrievable architecture context.",
                "Language detection is heuristic and based on the request, answers, and retrieved document text.",
            ],
            ru=[
                "Источник проекта сохранен, но репозиторий или архив еще не клонируется и не индексируется в этом milestone.",
                "Доступный архитектурный контекст берется только из загруженных документов.",
                "Определение языка эвристическое: по запросу, ответам и найденному тексту документов.",
            ],
        )
        latest_answer = prior_answers[-1].lower() if prior_answers else ""
        answer_text = " ".join(prior_answers).lower()

        if not payload.input_text.strip() and not payload.input_file_reference:
            missing_information.append(self._message(language, "missing_input"))
            questions.append(self._message(language, "question_input"))
        if not retrieved_chunks:
            missing_information.append(self._message(language, "missing_context"))
            questions.append(self._message(language, "question_context"))
        if not self._has_signal(retrieved_chunks, self._signals("acceptance")) and not any(
            signal in answer_text for signal in self._signals("acceptance")
        ):
            missing_information.append(self._message(language, "missing_acceptance"))
            questions.append(self._message(language, "question_acceptance"))
        if (
            payload.task_type == "bug"
            and not self._has_signal(retrieved_chunks, self._signals("bug"))
            and not all(any(signal in answer_text for signal in group) for group in (self._signals("actual"), self._signals("expected")))
        ):
            missing_information.append(self._message(language, "missing_bug"))
            questions.append(self._message(language, "question_bug"))
        if payload.task_type == "spike" and not self._has_signal(retrieved_chunks, self._signals("research")):
            missing_information.append(self._message(language, "missing_research"))
            questions.append(self._message(language, "question_research"))

        markers = NEEDS_MORE_INFO_MARKERS + RU_NEEDS_MORE_INFO_MARKERS
        if prior_answers and any(marker in latest_answer for marker in markers):
            missing_information.append(self._message(language, "missing_placeholders"))
            questions.append(self._message(language, "question_placeholders"))

        confidence = self._compute_confidence(retrieved_chunks, questions)
        if prior_answers and missing_information:
            confidence = min(0.74, round(confidence + 0.18, 2))
        elif prior_answers:
            confidence = max(0.76, confidence)

        scope = [payload.query]
        if payload.input_text.strip():
            scope.append(payload.input_text.strip()[:240])
        if project:
            scope.append(("Project: " if language == "en" else "Проект: ") + project.name)

        return InitialAnalysisOutput(
            request_summary=self._request_summary(payload, project, language),
            task_type=payload.task_type,
            language=language,
            understood_scope=scope,
            suspected_affected_components=self._affected_components(documents, retrieved_chunks),
            missing_information=missing_information,
            clarifying_questions=questions,
            preliminary_assumptions=assumptions,
            confidence=confidence,
        )

    @staticmethod
    def _is_ready_for_final_analysis(clarification: InitialAnalysisOutput, prior_answers: list[str]) -> bool:
        if not clarification.clarifying_questions and clarification.confidence >= 0.5:
            return True
        if prior_answers and clarification.confidence >= 0.75 and len(clarification.missing_information) <= 1:
            return True
        return False

    @staticmethod
    def _detect_payload_language(
        *,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
        prior_answers: list[str] | None = None,
    ) -> LanguageCode:
        return detect_language(
            payload.input_text,
            payload.query,
            " ".join(prior_answers or []),
            " ".join(document.extracted_text[:1000] for document in documents),
            " ".join(chunk.text[:1000] for chunk in retrieved_chunks),
            fallback="en",
        )

    @staticmethod
    def _localized_list(language: LanguageCode, *, en: list[str], ru: list[str]) -> list[str]:
        return ru if language == "ru" else en

    @staticmethod
    def _request_summary(
        payload: AnalysisRunCreateRequest,
        project: Project | None,
        language: LanguageCode,
    ) -> str:
        project_name = project.name if project else ("selected project" if language == "en" else "выбранного проекта")
        task_type = payload.task_type.replace("_", " ")
        if language == "ru":
            return f"Запрос типа '{task_type}' для проекта {project_name}: {payload.query}"
        return f"{task_type.title()} request for {project_name}: {payload.query}"

    @staticmethod
    def _signals(kind: str) -> tuple[str, ...]:
        signals = {
            "acceptance": (
                "acceptance",
                "criteria",
                "expected",
                "test",
                "validate",
                "coverage",
                "прием",
                "критер",
                "ожида",
                "тест",
                "провер",
                "покрыт",
            ),
            "bug": (
                "error",
                "bug",
                "actual",
                "expected",
                "reproduce",
                "ошиб",
                "баг",
                "факт",
                "ожида",
                "воспроиз",
            ),
            "actual": ("actual", "факт", "сейчас", "получаем"),
            "expected": ("expected", "ожида", "должн"),
            "research": ("decision", "option", "tradeoff", "research", "решен", "вариант", "компромисс", "исслед"),
        }
        return signals[kind]

    @staticmethod
    def _message(language: LanguageCode, key: str) -> str:
        messages = {
            "missing_input": {
                "en": "No detailed task input was provided.",
                "ru": "Не предоставлено подробное описание задачи.",
            },
            "question_input": {
                "en": "What exact behavior, defect, or research question should be analyzed?",
                "ru": "Какое поведение, дефект или исследовательский вопрос нужно проанализировать?",
            },
            "missing_context": {
                "en": "No grounded document chunks matched the request.",
                "ru": "По запросу не найдено подтвержденных фрагментов документов.",
            },
            "question_context": {
                "en": "Which source documents or architecture sections should ground this request?",
                "ru": "Какие документы или разделы архитектуры должны быть основой для этого запроса?",
            },
            "missing_acceptance": {
                "en": "Acceptance expectations are not explicit in the available context.",
                "ru": "В доступном контексте не хватает явных критериев приемки.",
            },
            "question_acceptance": {
                "en": "What acceptance criteria or observable outcome should confirm this work is done?",
                "ru": "Какие критерии приемки или наблюдаемый результат подтвердят, что работа выполнена?",
            },
            "missing_bug": {
                "en": "Bug reproduction details are missing.",
                "ru": "Не хватает деталей воспроизведения ошибки.",
            },
            "question_bug": {
                "en": "What are the actual behavior, expected behavior, and reproduction steps?",
                "ru": "Каковы фактическое поведение, ожидаемое поведение и шаги воспроизведения?",
            },
            "missing_research": {
                "en": "Research decision criteria are missing.",
                "ru": "Не хватает критериев решения для исследования.",
            },
            "question_research": {
                "en": "Which options, constraints, or decision criteria should the spike compare?",
                "ru": "Какие варианты, ограничения или критерии решения должен сравнить spike?",
            },
            "missing_placeholders": {
                "en": "The latest clarification answer still contains unresolved placeholders.",
                "ru": "Последний ответ на уточнение все еще содержит нерешенные placeholders.",
            },
            "question_placeholders": {
                "en": "Please replace unknown or TBD parts with concrete constraints or mark them out of scope.",
                "ru": "Замените неизвестные/TBD части конкретными ограничениями или явно исключите их из scope.",
            },
            "final_missing_context_note": {
                "en": "No matching chunks were retrieved from the selected documents, so the analysis stays minimal.",
                "ru": "В выбранных документах не найдено совпадающих фрагментов, поэтому анализ остается минимальным.",
            },
        }
        return messages[key][language]

    @staticmethod
    def _placeholder_output(clarification: InitialAnalysisOutput) -> AnalysisOutput:
        return AnalysisOutput(
            feature_summary=clarification.request_summary,
            affected_components=clarification.suspected_affected_components,
            backend_tasks=[],
            frontend_tasks=[],
            integration_tasks=[],
            db_changes=[],
            qa_tasks=[],
            observability_tasks=[],
            risks=[
                "Final implementation analysis is intentionally blocked until clarification is complete."
                if clarification.language == "en"
                else "Финальный анализ намеренно заблокирован до завершения уточнений."
            ],
            open_questions=clarification.clarifying_questions,
            assumptions=clarification.preliminary_assumptions,
            source_references=[],
            confidence=clarification.confidence,
        )

    def _build_output(
        self,
        *,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> AnalysisOutput:
        language = payload.language or "en"
        source_references = [
            chunk.to_source_reference(
                rationale=(
                    f"Retrieved for query '{payload.query}'."
                    if language == "en"
                    else f"Найдено по запросу '{payload.query}'."
                )
            )
            for chunk in retrieved_chunks
        ]

        if not retrieved_chunks:
            missing_context_note = self._message(language, "final_missing_context_note")
            return AnalysisOutput(
                feature_summary=(
                    f"{payload.query} Limited context was available in the uploaded documents."
                    if language == "en"
                    else f"{payload.query} В загруженных документах найден ограниченный контекст."
                ),
                affected_components=self._affected_components(documents, retrieved_chunks),
                backend_tasks=[],
                frontend_tasks=[],
                integration_tasks=[],
                db_changes=[],
                qa_tasks=[
                    self._make_task(
                        task_type="qa_tasks",
                        title=(
                            "Confirm the missing implementation details before execution"
                            if language == "en"
                            else "Уточнить недостающие детали реализации перед выполнением"
                        ),
                        description=missing_context_note,
                        why_needed=(
                            "The current document set does not provide enough grounded evidence for implementation tasks."
                            if language == "en"
                            else "Текущий набор документов не дает достаточно подтвержденного контекста для задач реализации."
                        ),
                        service_or_component="analysis-review",
                        acceptance_criteria=[
                            "Identify the missing specification sections or architecture decisions."
                            if language == "en"
                            else "Определить недостающие разделы спецификации или архитектурные решения.",
                            "Upload or link the missing documents before generating delivery tasks."
                            if language == "en"
                            else "Загрузить или связать недостающие документы перед генерацией задач.",
                        ],
                        dependencies=[],
                        assumptions=[],
                        source_refs=[],
                        confidence=0.2,
                    )
                ],
                observability_tasks=[],
                risks=[
                    "The available material is insufficient to derive grounded delivery tasks."
                    if language == "en"
                    else "Доступного материала недостаточно для обоснованных задач разработки."
                ],
                open_questions=[
                    "Which specification or architecture documents should be added so the analysis can cite concrete implementation details?"
                    if language == "en"
                    else "Какие спецификации или архитектурные документы нужно добавить, чтобы анализ ссылался на конкретные детали реализации?"
                ],
                assumptions=[
                    "The selected document set is incomplete for this feature."
                    if language == "en"
                    else "Выбранный набор документов неполон для этой задачи."
                ],
                source_references=source_references,
                confidence=0.2,
            )

        backend_tasks = self._maybe_backend_tasks(payload, retrieved_chunks)
        frontend_tasks = self._maybe_frontend_tasks(retrieved_chunks)
        integration_tasks = self._maybe_integration_tasks(retrieved_chunks)
        db_changes = self._maybe_db_tasks(retrieved_chunks)
        qa_tasks = self._build_qa_tasks(payload, retrieved_chunks)
        observability_tasks = self._maybe_observability_tasks(retrieved_chunks)
        risks = self._build_risks(retrieved_chunks, language=language)
        open_questions = self._build_open_questions(payload, documents, retrieved_chunks)
        assumptions = self._build_assumptions(payload, documents, retrieved_chunks)
        confidence = self._compute_confidence(retrieved_chunks, open_questions)

        return AnalysisOutput(
            feature_summary=self._feature_summary(payload, documents, retrieved_chunks),
            affected_components=self._affected_components(documents, retrieved_chunks),
            backend_tasks=backend_tasks,
            frontend_tasks=frontend_tasks,
            integration_tasks=integration_tasks,
            db_changes=db_changes,
            qa_tasks=qa_tasks,
            observability_tasks=observability_tasks,
            risks=risks,
            open_questions=open_questions,
            assumptions=assumptions,
            source_references=source_references,
            confidence=confidence,
        )

    def _load_documents(self, document_ids: list[UUID]) -> list[Document]:
        if not document_ids:
            return []
        statement = select(Document).where(Document.id.in_(document_ids))
        return list(self.db.scalars(statement).all())

    def _build_generated_task_rows(self, output: AnalysisOutput) -> list[GeneratedTask]:
        rows: list[GeneratedTask] = []
        for section_name in TASK_SECTION_NAMES:
            for task in getattr(output, section_name):
                rows.append(
                    GeneratedTask(
                        task_type=section_name,
                        title=task.title,
                        description=task.description,
                        why_needed=task.why_needed,
                        service_or_component=task.service_or_component,
                        acceptance_criteria=task.acceptance_criteria,
                        dependencies=task.dependencies,
                        assumptions=task.assumptions,
                        source_refs=[ref.model_dump(mode="json") for ref in task.source_refs],
                        confidence=task.confidence,
                    )
                )
        return rows

    def _build_validation_notes(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> str:
        notes = [
            (
                "Deterministic retrieval-based analysis only; no LLM generation is active in this milestone."
                if payload.language != "ru"
                else "Анализ детерминированный и основан на поиске; LLM-генерация в этом milestone не активна."
            ),
            (
                f"Vector similarity available: {'yes' if self.retrieval.vector_search_enabled() else 'no'}"
                if payload.language != "ru"
                else f"Векторное сходство доступно: {'да' if self.retrieval.vector_search_enabled() else 'нет'}"
            ),
            f"Retrieved chunks: {len(retrieved_chunks)}" if payload.language != "ru" else f"Найдено фрагментов: {len(retrieved_chunks)}",
        ]
        if payload.document_ids and len(documents) != len(payload.document_ids):
            notes.append(
                "One or more requested documents were not found."
                if payload.language != "ru"
                else "Один или несколько выбранных документов не найдены."
            )
        if not retrieved_chunks:
            notes.append(
                "No grounded chunk matches were found for the requested query."
                if payload.language != "ru"
                else "По запросу не найдено подтвержденных совпадений во фрагментах."
            )
        return " ".join(notes)

    def _feature_summary(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> str:
        filenames = sorted({chunk.filename for chunk in retrieved_chunks}) or [document.filename for document in documents]
        file_list = ", ".join(filenames[:3])
        if payload.language == "ru":
            return (
                f"{payload.query} Найден подтвержденный контекст: {len(retrieved_chunks)} фрагмент(ов)"
                f" в {len(filenames)} документ(ах): {file_list}."
            )
        return (
            f"{payload.query} Grounded evidence was retrieved from {len(retrieved_chunks)} chunk(s)"
            f" across {len(filenames)} document(s): {file_list}."
        )

    def _affected_components(self, documents: list[Document], retrieved_chunks: list[RetrievedChunk]) -> list[str]:
        components: set[str] = set()
        for document in documents:
            components.add(document.kind)
            components.add(document.filename)
        for chunk in retrieved_chunks:
            components.add(chunk.kind)
            filename_stem = chunk.filename.rsplit(".", 1)[0]
            components.add(filename_stem)
            for candidate in self._extract_components(chunk.text):
                components.add(candidate)
        return sorted(component for component in components if component)

    def _maybe_backend_tasks(
        self,
        payload: AnalysisRunCreateRequest,
        retrieved_chunks: list[RetrievedChunk],
    ) -> list[GeneratedTaskPayload]:
        if not retrieved_chunks:
            return []
        signals = ("api", "backend", "service", "fastapi", "endpoint", "analysis", "retrieval")
        if not self._has_signal(retrieved_chunks, signals):
            return []
        refs = self._task_refs(retrieved_chunks, "Evidence describing the backend-facing behavior.")
        return [
            self._make_task(
                task_type="backend_tasks",
                title="Implement the API and service changes described by the retrieved specification",
                description=(
                    f"Translate the grounded backend requirements for '{payload.query}' into service and route updates"
                    " while keeping the response contract and source references intact."
                ),
                why_needed="The retrieved chunks describe server-side behavior that the current implementation must honor.",
                service_or_component=self._primary_component(retrieved_chunks, fallback="backend"),
                acceptance_criteria=[
                    "Backend routes and services reflect the grounded document behavior.",
                    "Returned payloads preserve explicit source references and confidence values.",
                ],
                dependencies=[],
                assumptions=["Only deterministic retrieval-backed behavior is in scope for this milestone."],
                source_refs=refs,
                confidence=0.72,
            )
        ]

    def _maybe_frontend_tasks(self, retrieved_chunks: list[RetrievedChunk]) -> list[GeneratedTaskPayload]:
        signals = ("frontend", "ui", "screen", "react", "client")
        if not self._has_signal(retrieved_chunks, signals):
            return []
        return [
            self._make_task(
                task_type="frontend_tasks",
                title="Align the client flows with the retrieved feature behavior",
                description="Review the referenced chunks for any UI-facing fields or flows that the client must expose.",
                why_needed="The documents mention client-visible behavior that should stay consistent with the API output.",
                service_or_component="frontend",
                acceptance_criteria=[
                    "Client interactions reflect the documented request and response flow.",
                    "Displayed analysis details preserve the cited source references.",
                ],
                dependencies=["Implement the corresponding backend contract first."],
                assumptions=[],
                source_refs=self._task_refs(retrieved_chunks, "Frontend-facing requirement signal."),
                confidence=0.55,
            )
        ]

    def _maybe_integration_tasks(self, retrieved_chunks: list[RetrievedChunk]) -> list[GeneratedTaskPayload]:
        signals = ("integration", "external", "webhook", "jira", "api client")
        if not self._has_signal(retrieved_chunks, signals):
            return []
        return [
            self._make_task(
                task_type="integration_tasks",
                title="Verify the external integration boundaries called out by the documents",
                description="Keep integration points explicit and manually approved while the backend contract evolves.",
                why_needed="The retrieved material references external systems that can break if the payload shape drifts.",
                service_or_component="integration",
                acceptance_criteria=[
                    "External handoff points are documented and validated against the strict analysis contract.",
                    "No automatic Jira creation is introduced without human approval.",
                ],
                dependencies=[],
                assumptions=["Integration execution remains manual in this milestone."],
                source_refs=self._task_refs(retrieved_chunks, "Integration-related evidence."),
                confidence=0.6,
            )
        ]

    def _maybe_db_tasks(self, retrieved_chunks: list[RetrievedChunk]) -> list[GeneratedTaskPayload]:
        signals = ("database", "schema", "postgres", "table", "migration", "chunk")
        if not self._has_signal(retrieved_chunks, signals):
            return []
        return [
            self._make_task(
                task_type="db_changes",
                title="Apply the persistence changes implied by the retrieved documents",
                description="Persist analysis data and retrieval metadata in a way that keeps downstream review deterministic.",
                why_needed="The grounded context references data structures that must be stored consistently for later review.",
                service_or_component="postgresql",
                acceptance_criteria=[
                    "Database changes remain scoped to analysis and retrieval support.",
                    "Stored records preserve enough context to reconstruct source-backed output.",
                ],
                dependencies=[],
                assumptions=["Embedding generation stays out of scope until it can be wired robustly."],
                source_refs=self._task_refs(retrieved_chunks, "Persistence-related evidence."),
                confidence=0.68,
            )
        ]

    def _build_qa_tasks(
        self,
        payload: AnalysisRunCreateRequest,
        retrieved_chunks: list[RetrievedChunk],
    ) -> list[GeneratedTaskPayload]:
        language = payload.language or "en"
        if language == "ru":
            return [
                self._make_task(
                    task_type="qa_tasks",
                    title="Добавить покрытие для анализа на основе найденного контекста",
                    description=(
                        f"Проверить детерминированный поток анализа для '{payload.query}', включая фильтры поиска,"
                        " ссылки на источники и строгую форму ответа."
                    ),
                    why_needed="Пайплайн зависит от подтвержденного контекста, поэтому регрессии в поиске и JSON-форме должны обнаруживаться быстро.",
                    service_or_component="tests",
                    acceptance_criteria=[
                        "Тесты проверяют строгий верхнеуровневый контракт ответа.",
                        "Тесты проверяют наличие ссылок на источники и confidence.",
                    ],
                    dependencies=[],
                    assumptions=[],
                    source_refs=self._task_refs(retrieved_chunks, "Покрытие тестами должно учитывать эти требования из источников."),
                    confidence=0.8,
                )
            ]
        return [
            self._make_task(
                task_type="qa_tasks",
                title="Add coverage for retrieval-backed analysis generation",
                description=(
                    f"Validate the deterministic analysis flow for '{payload.query}', including retrieval filters,"
                    " source references, and strict contract shape."
                ),
                why_needed="This milestone depends on grounded outputs, so regressions in retrieval or JSON shape should fail fast.",
                service_or_component="tests",
                acceptance_criteria=[
                    "Tests assert the strict top-level response contract.",
                    "Tests verify source references and confidence fields are present.",
                ],
                dependencies=[],
                assumptions=[],
                source_refs=self._task_refs(retrieved_chunks, "Test coverage should track these referenced requirements."),
                confidence=0.8,
            )
        ]

    def _maybe_observability_tasks(self, retrieved_chunks: list[RetrievedChunk]) -> list[GeneratedTaskPayload]:
        signals = ("log", "metric", "observability", "trace", "monitor")
        if not self._has_signal(retrieved_chunks, signals):
            return []
        return [
            self._make_task(
                task_type="observability_tasks",
                title="Instrument retrieval and analysis execution points referenced by the docs",
                description="Capture enough runtime signals to debug missing context, low confidence, or retrieval mismatches.",
                why_needed="The documents call out runtime visibility, and this pipeline depends on deterministic evidence selection.",
                service_or_component="observability",
                acceptance_criteria=[
                    "Key retrieval and analysis events are traceable in logs or metrics.",
                    "Low-context runs can be diagnosed without inspecting the database manually.",
                ],
                dependencies=[],
                assumptions=[],
                source_refs=self._task_refs(retrieved_chunks, "Observability-related evidence."),
                confidence=0.5,
            )
        ]

    def _build_risks(self, retrieved_chunks: list[RetrievedChunk], *, language: LanguageCode = "en") -> list[str]:
        if language == "ru":
            risks = [
                "Генерация embeddings и pgvector similarity остаются выключенными до надежного пайплайна embeddings."
            ]
            if len(retrieved_chunks) < 2:
                risks.append("Анализ основан на узком контексте и может пропустить междокументные ограничения.")
            if not self._has_signal(retrieved_chunks, self._signals("acceptance")):
                risks.append("Критерии приемки выведены из ограниченного контекста и требуют проверки человеком.")
            return risks
        risks = [
            "Embedding generation and pgvector similarity remain disabled until a robust embedding pipeline is added."
        ]
        if len(retrieved_chunks) < 2:
            risks.append("The analysis is grounded in a narrow slice of context and may miss cross-document constraints.")
        if not self._has_signal(retrieved_chunks, self._signals("acceptance")):
            risks.append("Acceptance expectations were inferred from limited context and should be reviewed by a human.")
        return risks

    def _build_open_questions(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> list[str]:
        questions: list[str] = []
        language = payload.language or "en"
        if payload.document_ids and len(documents) != len(payload.document_ids):
            questions.append(
                "Should missing requested documents block analysis creation instead of producing a partial result?"
                if language == "en"
                else "Должны ли отсутствующие выбранные документы блокировать анализ вместо частичного результата?"
            )
        if not self._has_signal(retrieved_chunks, ("frontend", "ui", "screen", "интерфейс", "экран", "клиент")):
            questions.append(
                "Is there any frontend scope for this feature, or should the frontend task list remain empty?"
                if language == "en"
                else "Есть ли frontend-scope для этой задачи или список frontend-задач должен остаться пустым?"
            )
        if not self.retrieval.vector_search_enabled():
            questions.append(
                "Which embedding model and ingestion trigger should activate pgvector similarity in the next milestone?"
                if language == "en"
                else "Какая модель embeddings и какой триггер ingest должны включить pgvector similarity в следующем milestone?"
            )
        return questions

    def _build_assumptions(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> list[str]:
        if payload.language == "ru":
            assumptions = [
                "В этом milestone доступны только загруженные документы `.txt` и `.md` как подтвержденные источники.",
                "Детерминированного ранжирования достаточно до внедрения реальных embeddings.",
            ]
            if not documents and payload.document_kind:
                assumptions.append(f"Фильтр типа документа '{payload.document_kind}' используется без явно выбранных документов.")
            if retrieved_chunks:
                assumptions.append("Самые релевантные найденные фрагменты считаются представительными для контекста запроса.")
            return assumptions
        assumptions = [
            "Only uploaded `.txt` and `.md` documents are available as grounded sources in this milestone.",
            "The deterministic retrieval ranking is sufficient until real embeddings are introduced.",
        ]
        if not documents and payload.document_kind:
            assumptions.append(f"Document kind filter '{payload.document_kind}' is being used without explicitly selected documents.")
        if retrieved_chunks:
            assumptions.append("The highest-ranked retrieved chunks are representative of the requested feature context.")
        return assumptions

    @staticmethod
    def _compute_confidence(retrieved_chunks: list[RetrievedChunk], open_questions: list[str]) -> float:
        base = min(0.9, 0.45 + (0.08 * len(retrieved_chunks)))
        penalty = min(0.25, 0.05 * len(open_questions))
        return round(max(0.2, base - penalty), 2)

    @staticmethod
    def _extract_components(text: str) -> set[str]:
        components: set[str] = set()
        for token in text.replace("/", " ").replace("`", " ").split():
            cleaned = token.strip(".,:;()[]{}")
            if len(cleaned) < 4:
                continue
            if any(character.isupper() for character in cleaned) or "-" in cleaned or "_" in cleaned:
                components.add(cleaned)
        return components

    @staticmethod
    def _has_signal(retrieved_chunks: Iterable[RetrievedChunk], signals: tuple[str, ...]) -> bool:
        haystack = " ".join(chunk.text.lower() for chunk in retrieved_chunks)
        return has_any(haystack, signals)

    @staticmethod
    def _primary_component(retrieved_chunks: list[RetrievedChunk], fallback: str) -> str:
        if not retrieved_chunks:
            return fallback
        return retrieved_chunks[0].chunk_metadata.get("filename") or retrieved_chunks[0].filename or fallback

    @staticmethod
    def _task_refs(retrieved_chunks: list[RetrievedChunk], rationale: str) -> list[SourceReference]:
        return [chunk.to_source_reference(rationale) for chunk in retrieved_chunks[:3]]

    @staticmethod
    def _make_task(
        *,
        task_type: str,
        title: str,
        description: str,
        why_needed: str,
        service_or_component: str,
        acceptance_criteria: list[str],
        dependencies: list[str],
        assumptions: list[str],
        source_refs: list[SourceReference],
        confidence: float,
    ) -> GeneratedTaskPayload:
        return GeneratedTaskPayload(
            title=title,
            description=description,
            why_needed=why_needed,
            service_or_component=service_or_component,
            acceptance_criteria=acceptance_criteria,
            dependencies=dependencies,
            assumptions=assumptions,
            source_refs=source_refs,
            confidence=confidence,
        )

    @staticmethod
    def _to_response(run: AnalysisRun) -> AnalysisRunResponse:
        output = AnalysisOutput.model_validate(run.output_payload)
        clarification = (
            InitialAnalysisOutput.model_validate(run.clarification_payload)
            if run.clarification_payload
            else None
        )
        return AnalysisRunResponse(
            id=run.id,
            status=run.status,
            project_id=run.project_id,
            project_name=run.project.name if run.project else None,
            task_type=run.task_type,
            input_type=run.input_type,
            input_text=run.input_text or "",
            input_file_reference=run.input_file_reference,
            language=(run.request_payload or {}).get("language") or (clarification.language if clarification else "en"),
            review_status=run.review_status,
            reviewer_note=run.reviewer_note or "",
            document_id=run.document_id,
            request_payload=run.request_payload or {},
            clarification=clarification,
            clarification_rounds=[
                ClarificationRoundResponse.model_validate(round_)
                for round_ in run.clarification_rounds
            ],
            validation_notes=run.validation_notes,
            created_at=run.created_at,
            **output.model_dump(),
        )
