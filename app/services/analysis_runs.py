from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.analysis_run import AnalysisRun
from app.models.document import Document
from app.models.generated_task import GeneratedTask
from app.schemas.analysis import (
    AnalysisOutput,
    AnalysisRunCreateRequest,
    AnalysisRunResponse,
    GeneratedTaskPayload,
    SourceReference,
)
from app.services.retrieval import RetrievalService, RetrievedChunk


TASK_SECTION_NAMES = (
    "backend_tasks",
    "frontend_tasks",
    "integration_tasks",
    "db_changes",
    "qa_tasks",
    "observability_tasks",
)


class AnalysisRunService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.retrieval = RetrievalService(db)

    def create_run(self, payload: AnalysisRunCreateRequest) -> AnalysisRunResponse:
        requested_documents = self._load_documents(payload.document_ids)
        retrieved_chunks = self.retrieval.search_chunks(
            query=payload.query,
            document_ids=payload.document_ids,
            document_kind=payload.document_kind,
            metadata_filters=payload.metadata_filters,
            limit=payload.max_chunks,
        )
        output = self._build_output(payload=payload, documents=requested_documents, retrieved_chunks=retrieved_chunks)
        validation_notes = self._build_validation_notes(payload, requested_documents, retrieved_chunks)

        run = AnalysisRun(
            document_id=payload.document_ids[0] if payload.document_ids else None,
            status="completed",
            request_payload=payload.model_dump(mode="json"),
            output_payload=output.model_dump(mode="json"),
            validation_notes=validation_notes,
        )
        run.generated_tasks = self._build_generated_task_rows(output)

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return self._to_response(run)

    def get_run(self, analysis_run_id: UUID) -> AnalysisRunResponse | None:
        statement = (
            select(AnalysisRun)
            .options(selectinload(AnalysisRun.generated_tasks))
            .where(AnalysisRun.id == analysis_run_id)
        )
        run = self.db.scalars(statement).first()
        if run is None:
            return None
        return self._to_response(run)

    def _build_output(
        self,
        *,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> AnalysisOutput:
        source_references = [
            chunk.to_source_reference(rationale=f"Retrieved for query '{payload.query}'.")
            for chunk in retrieved_chunks
        ]

        if not retrieved_chunks:
            missing_context_note = (
                "No matching chunks were retrieved from the selected documents, so the analysis stays minimal."
            )
            return AnalysisOutput(
                feature_summary=f"{payload.query} Limited context was available in the uploaded documents.",
                affected_components=self._affected_components(documents, retrieved_chunks),
                backend_tasks=[],
                frontend_tasks=[],
                integration_tasks=[],
                db_changes=[],
                qa_tasks=[
                    self._make_task(
                        task_type="qa_tasks",
                        title="Confirm the missing implementation details before execution",
                        description=missing_context_note,
                        why_needed="The current document set does not provide enough grounded evidence for implementation tasks.",
                        service_or_component="analysis-review",
                        acceptance_criteria=[
                            "Identify the missing specification sections or architecture decisions.",
                            "Upload or link the missing documents before generating delivery tasks.",
                        ],
                        dependencies=[],
                        assumptions=[],
                        source_refs=[],
                        confidence=0.2,
                    )
                ],
                observability_tasks=[],
                risks=["The available material is insufficient to derive grounded delivery tasks."],
                open_questions=[
                    "Which specification or architecture documents should be added so the analysis can cite concrete implementation details?"
                ],
                assumptions=["The selected document set is incomplete for this feature."],
                source_references=source_references,
                confidence=0.2,
            )

        backend_tasks = self._maybe_backend_tasks(payload, retrieved_chunks)
        frontend_tasks = self._maybe_frontend_tasks(retrieved_chunks)
        integration_tasks = self._maybe_integration_tasks(retrieved_chunks)
        db_changes = self._maybe_db_tasks(retrieved_chunks)
        qa_tasks = self._build_qa_tasks(payload, retrieved_chunks)
        observability_tasks = self._maybe_observability_tasks(retrieved_chunks)
        risks = self._build_risks(retrieved_chunks)
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
            "Deterministic retrieval-based analysis only; no LLM generation is active in this milestone.",
            f"Vector similarity available: {'yes' if self.retrieval.vector_search_enabled() else 'no'}",
            f"Retrieved chunks: {len(retrieved_chunks)}",
        ]
        if payload.document_ids and len(documents) != len(payload.document_ids):
            notes.append("One or more requested documents were not found.")
        if not retrieved_chunks:
            notes.append("No grounded chunk matches were found for the requested query.")
        return " ".join(notes)

    def _feature_summary(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> str:
        filenames = sorted({chunk.filename for chunk in retrieved_chunks}) or [document.filename for document in documents]
        file_list = ", ".join(filenames[:3])
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

    def _build_risks(self, retrieved_chunks: list[RetrievedChunk]) -> list[str]:
        risks = [
            "Embedding generation and pgvector similarity remain disabled until a robust embedding pipeline is added."
        ]
        if len(retrieved_chunks) < 2:
            risks.append("The analysis is grounded in a narrow slice of context and may miss cross-document constraints.")
        if not self._has_signal(retrieved_chunks, ("acceptance", "criteria", "test", "validate")):
            risks.append("Acceptance expectations were inferred from limited context and should be reviewed by a human.")
        return risks

    def _build_open_questions(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> list[str]:
        questions: list[str] = []
        if payload.document_ids and len(documents) != len(payload.document_ids):
            questions.append("Should missing requested documents block analysis creation instead of producing a partial result?")
        if not self._has_signal(retrieved_chunks, ("frontend", "ui", "screen")):
            questions.append("Is there any frontend scope for this feature, or should the frontend task list remain empty?")
        if not self.retrieval.vector_search_enabled():
            questions.append("Which embedding model and ingestion trigger should activate pgvector similarity in the next milestone?")
        return questions

    def _build_assumptions(
        self,
        payload: AnalysisRunCreateRequest,
        documents: list[Document],
        retrieved_chunks: list[RetrievedChunk],
    ) -> list[str]:
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
        return any(signal in haystack for signal in signals)

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
        return AnalysisRunResponse(
            id=run.id,
            status=run.status,
            document_id=run.document_id,
            request_payload=run.request_payload or {},
            validation_notes=run.validation_notes,
            created_at=run.created_at,
            **output.model_dump(),
        )
