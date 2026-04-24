from app.services.language import LanguageCode, normalize_language


TEXT: dict[str, dict[LanguageCode, str]] = {
    "app_name": {"en": "AI System Analyst", "ru": "AI Системный аналитик"},
    "sidebar_copy": {
        "en": "Grounded project analysis with clarification, review, and controlled export preview.",
        "ru": "Проектный анализ с уточнениями, ревью и контролируемым предпросмотром экспорта.",
    },
    "nav_projects": {"en": "Projects", "ru": "Проекты"},
    "nav_new_analysis": {"en": "New Analysis", "ru": "Новый анализ"},
    "nav_clarifications": {"en": "Clarifications", "ru": "Уточнения"},
    "nav_results": {"en": "Results", "ru": "Результаты"},
    "nav_documents": {"en": "Documents", "ru": "Документы"},
    "nav_api_docs": {"en": "API Docs", "ru": "API docs"},
    "dashboard_title": {"en": "Internal Review Dashboard", "ru": "Панель внутреннего анализа"},
    "dashboard_lead": {
        "en": "Project-aware analysis starts with clarification when the request lacks enough grounded information for final output.",
        "ru": "Проектный анализ сначала задает уточняющие вопросы, если данных недостаточно для итогового результата.",
    },
    "projects": {"en": "Projects", "ru": "Проекты"},
    "project_sources": {"en": "Project Sources", "ru": "Источники проектов"},
    "create_project": {"en": "Create project", "ru": "Создать проект"},
    "stored_projects": {"en": "Stored projects", "ru": "Сохраненные проекты"},
    "name": {"en": "Name", "ru": "Название"},
    "description": {"en": "Description", "ru": "Описание"},
    "source_type": {"en": "Source type", "ru": "Тип источника"},
    "repository_url": {"en": "Repository URL", "ru": "URL репозитория"},
    "archive_file": {"en": "Archive file", "ru": "Архив проекта"},
    "github": {"en": "GitHub", "ru": "GitHub"},
    "uploaded_archive": {"en": "Uploaded archive", "ru": "Загруженный архив"},
    "no_projects": {"en": "No projects yet.", "ru": "Проектов пока нет."},
    "new_analysis": {"en": "New analysis", "ru": "Новый анализ"},
    "documents": {"en": "Documents", "ru": "Документы"},
    "upload_sources": {"en": "Upload and Inspect Sources", "ru": "Загрузка и просмотр источников"},
    "upload_document": {"en": "Upload document", "ru": "Загрузить документ"},
    "stored_documents": {"en": "Stored documents", "ru": "Сохраненные документы"},
    "document_kind": {"en": "Document kind", "ru": "Тип документа"},
    "source_file": {"en": "Source file", "ru": "Файл источника"},
    "upload": {"en": "Upload", "ru": "Загрузить"},
    "no_documents": {"en": "No uploaded documents yet.", "ru": "Загруженных документов пока нет."},
    "create_analysis_run": {"en": "Create Analysis Run", "ru": "Создать запрос анализа"},
    "analysis_lead": {
        "en": "Select a project, task type, and input. The system will ask for clarification before final output when context is thin.",
        "ru": "Выберите проект, тип задачи и входные данные. Если контекста мало, система сначала задаст уточняющие вопросы.",
    },
    "project": {"en": "Project", "ru": "Проект"},
    "select_project": {"en": "Select a project", "ru": "Выберите проект"},
    "task_type": {"en": "Task type", "ru": "Тип задачи"},
    "initial_input": {"en": "Initial input", "ru": "Исходное описание"},
    "initial_input_hint": {
        "en": "Describe the request, bug, change, or research question.",
        "ru": "Опишите запрос, ошибку, изменение или исследовательский вопрос.",
    },
    "initial_input_file": {"en": "Initial input file", "ru": "Файл с исходным описанием"},
    "query": {"en": "Query", "ru": "Запрос"},
    "query_default": {
        "en": "Summarize the implementation work required by the selected documents.",
        "ru": "Опишите необходимые работы по выбранным документам.",
    },
    "document_kind_filter": {"en": "Document kind filter", "ru": "Фильтр типа документа"},
    "optional_spec": {"en": "Optional, e.g. specification", "ru": "Необязательно, например specification"},
    "max_chunks": {"en": "Max chunks", "ru": "Максимум фрагментов"},
    "select_documents": {"en": "Select documents", "ru": "Выберите документы"},
    "start_analysis": {"en": "Start analysis run", "ru": "Запустить анализ"},
    "upload_before_analysis": {
        "en": "Upload a document before starting an analysis run.",
        "ru": "Загрузите документ перед запуском анализа.",
    },
    "clarifications": {"en": "Clarifications", "ru": "Уточнения"},
    "results": {"en": "Results", "ru": "Результаты"},
    "analysis_runs": {"en": "Analysis Runs", "ru": "Запросы анализа"},
    "summary": {"en": "Summary", "ru": "Итог"},
    "run_status": {"en": "Run status", "ru": "Статус"},
    "review_status": {"en": "Review status", "ru": "Статус ревью"},
    "confidence": {"en": "Confidence", "ru": "Уверенность"},
    "created": {"en": "Created", "ru": "Создано"},
    "no_analysis_runs": {"en": "No analysis runs yet.", "ru": "Запросов анализа пока нет."},
    "review_workflow": {"en": "Review workflow", "ru": "Ревью"},
    "reviewer_note": {"en": "Reviewer note", "ru": "Заметка ревьюера"},
    "save_review": {"en": "Save review decision", "ru": "Сохранить решение"},
    "validation_notes": {"en": "Validation notes", "ru": "Заметки проверки"},
    "structured_output": {"en": "Structured review output", "ru": "Структурированный результат"},
    "current_understanding": {"en": "Current understanding", "ru": "Текущее понимание"},
    "clarification_rounds": {"en": "Clarification rounds", "ru": "Раунды уточнений"},
    "your_answer": {"en": "Your clarification answer", "ru": "Ваш ответ на уточнения"},
    "submit_clarification": {"en": "Submit clarification", "ru": "Отправить уточнение"},
    "generated_sections": {"en": "Generated task sections", "ru": "Секции задач"},
    "preview_export": {"en": "Preview Jira export", "ru": "Предпросмотр Jira export"},
    "none": {"en": "None", "ru": "Нет"},
    "pending": {"en": "Pending", "ru": "Ожидает ответа"},
    "language": {"en": "Language", "ru": "Язык"},
    "source": {"en": "Source", "ru": "Источник"},
    "reference": {"en": "Reference", "ru": "Ссылка"},
    "ingestion": {"en": "Ingestion", "ru": "Ингестия"},
    "boundary": {"en": "Boundary", "ru": "Граница"},
    "analysis_requests": {"en": "Analysis requests", "ru": "Запросы анализа"},
}


STATUS_LABELS: dict[str, dict[LanguageCode, str]] = {
    "draft": {"en": "draft", "ru": "черновик"},
    "needs_clarification": {"en": "needs clarification", "ru": "нужны уточнения"},
    "clarification_answered": {"en": "clarification answered", "ru": "уточнение получено"},
    "ready_for_final_analysis": {"en": "ready for final analysis", "ru": "готово к финальному анализу"},
    "completed": {"en": "completed", "ru": "завершено"},
    "reviewed": {"en": "reviewed", "ru": "проверено"},
    "approved": {"en": "approved", "ru": "одобрено"},
    "rejected": {"en": "rejected", "ru": "отклонено"},
}


TASK_TYPE_LABELS: dict[str, dict[LanguageCode, str]] = {
    "feature": {"en": "Feature", "ru": "Фича"},
    "enhancement": {"en": "Enhancement/change", "ru": "Улучшение/изменение"},
    "bug": {"en": "Bug", "ru": "Ошибка"},
    "technical_task": {"en": "Technical task", "ru": "Техническая задача"},
    "spike": {"en": "Spike/research", "ru": "Исследование"},
}


def t(key: str, language: str | None = None) -> str:
    normalized = normalize_language(language)
    return TEXT.get(key, {}).get(normalized) or TEXT.get(key, {}).get("en") or key


def status_label(status: str, language: str | None = None) -> str:
    normalized = normalize_language(language)
    return STATUS_LABELS.get(status, {}).get(normalized) or status.replace("_", " ")


def task_type_label(task_type: str, language: str | None = None) -> str:
    normalized = normalize_language(language)
    return TASK_TYPE_LABELS.get(task_type, {}).get(normalized) or task_type.replace("_", " ")
