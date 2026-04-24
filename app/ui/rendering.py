from datetime import datetime
from html import escape

from app.schemas.analysis import AnalysisRunListItem, AnalysisRunResponse, GeneratedTaskPayload, SourceReference
from app.schemas.document import DocumentDetail, DocumentListItem
from app.schemas.export import JiraExportPreviewResponse, JiraExportResponse
from app.schemas.project import ProjectListItem, ProjectResponse
from app.ui.i18n import status_label, t, task_type_label


TASK_SECTIONS = (
    ("backend_tasks", "Backend Tasks"),
    ("frontend_tasks", "Frontend Tasks"),
    ("integration_tasks", "Integration Tasks"),
    ("db_changes", "DB Changes"),
    ("qa_tasks", "QA Tasks"),
    ("observability_tasks", "Observability Tasks"),
)


def render_page(*, title: str, current_path: str, content: str, language: str = "en") -> str:
    navigation = "".join(
        _nav_link(label, href, current_path == href)
        for label, href in (
            (t("nav_projects", language), "/projects"),
            (t("nav_new_analysis", language), "/analysis-runs/new"),
            (t("nav_clarifications", language), "/clarifications"),
            (t("nav_results", language), "/results"),
            (t("nav_documents", language), "/documents"),
            (t("nav_api_docs", language), "/docs"),
        )
    )
    language_switcher = "".join(
        f"<a class='language-option {'active' if language == code else ''}' href='{current_path}?lang={code}'>{label}</a>"
        for code, label in (("ru", "RU"), ("en", "EN"))
    )
    return f"""<!DOCTYPE html>
<html lang="{escape(language)}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)} - {escape(t("app_name", language))}</title>
    <link rel="stylesheet" href="/static/internal.css">
  </head>
  <body>
    <div class="shell">
      <aside class="sidebar">
        <h1>{escape(t("app_name", language))}</h1>
        <p class="sidebar-copy">{escape(t("sidebar_copy", language))}</p>
        <nav class="nav">{navigation}</nav>
        <div class="language-switcher" aria-label="{escape(t("language", language))}">{language_switcher}</div>
      </aside>
      <main class="content">{content}</main>
    </div>
  </body>
</html>"""


def render_dashboard(documents: list[DocumentListItem], runs: list[AnalysisRunListItem], *, language: str = "en") -> str:
    recent_documents = "".join(
        f"<li><a href='/documents/{document.id}'>{escape(document.filename)}</a><span>{escape(document.kind)}</span></li>"
        for document in documents[:5]
    ) or f"<li class='empty'>{escape(t('no_documents', language))}</li>"
    recent_runs = "".join(
        f"<li><a href='/analysis-runs/{run.id}'>{escape(run.feature_summary)}</a>{_review_badge(run.review_status)}</li>"
        for run in runs[:5]
    ) or f"<li class='empty'>{escape(t('no_analysis_runs', language))}</li>"
    approved_count = sum(1 for run in runs if run.review_status == "approved")
    return render_page(
        title=t("dashboard_title", language),
        current_path="/",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Milestone 5</p>
            <h2>{escape(t("dashboard_title", language))}</h2>
            <p class="lead">{escape(t("dashboard_lead", language))}</p>
          </div>
        </header>
        <section class="stats-grid">
          {_stat_card(t("documents", language), str(len(documents)), "Uploaded `.txt` and `.md` sources" if language == "en" else "Загруженные `.txt` и `.md` источники")}
          {_stat_card(t("analysis_runs", language), str(len(runs)), "Persisted structured outputs" if language == "en" else "Сохраненные структурированные результаты")}
          {_stat_card(status_label("approved", language).title(), str(approved_count), "Runs eligible for export preview confirmation" if language == "en" else "Запросы, доступные для предпросмотра экспорта")}
        </section>
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header">
              <h3>Recent Documents</h3>
              <a class="text-link" href="/documents">Manage documents</a>
            </div>
            <ul class="link-list">{recent_documents}</ul>
          </article>
          <article class="panel">
            <div class="panel-header">
              <h3>Recent Analysis Runs</h3>
              <a class="text-link" href="/analysis-runs">See all runs</a>
            </div>
            <ul class="link-list">{recent_runs}</ul>
          </article>
        </section>
        """,
    )


def render_projects_page(projects: list[ProjectListItem], *, error: str | None = None, language: str = "en") -> str:
    rows = "".join(
        f"""
        <tr>
          <td><a href="/projects/{project.id}">{escape(project.name)}</a></td>
          <td>{escape(project.source_type)}</td>
          <td>{escape(project.ingestion_status)}</td>
          <td>{project.analysis_count}</td>
          <td>{_format_dt(project.created_at)}</td>
        </tr>
        """
        for project in projects
    ) or f"<tr><td colspan='5' class='empty'>{escape(t('no_projects', language))}</td></tr>"
    return render_page(
        title=t("projects", language),
        current_path="/projects",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(t("projects", language))}</p>
            <h2>{escape(t("project_sources", language))}</h2>
          </div>
        </header>
        {_flash(error, tone='error') if error else ''}
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("create_project", language))}</h3></div>
            <form method="post" action="/projects" enctype="multipart/form-data" class="stack-form">
              <label>{escape(t("name", language))}<input type="text" name="name" required></label>
              <label>{escape(t("description", language))}<textarea name="description" rows="3"></textarea></label>
              <label>{escape(t("source_type", language))}
                <select name="source_type" required>
                  <option value="github">{escape(t("github", language))}</option>
                  <option value="archive">{escape(t("uploaded_archive", language))}</option>
                </select>
              </label>
              <label>{escape(t("repository_url", language))}<input type="url" name="repository_url" placeholder="https://github.com/org/repo"></label>
              <label>{escape(t("archive_file", language))}<input type="file" name="archive" accept=".zip,.tar,.gz,.tgz"></label>
              <button type="submit">{escape(t("create_project", language))}</button>
            </form>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("stored_projects", language))}</h3></div>
            <table>
              <thead><tr><th>{escape(t("name", language))}</th><th>{escape(t("source", language))}</th><th>{escape(t("ingestion", language))}</th><th>{escape(t("analysis_runs", language))}</th><th>{escape(t("created", language))}</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </article>
        </section>
        """,
    )


def render_project_detail(project: ProjectResponse, runs: list[AnalysisRunListItem], *, language: str = "en") -> str:
    project_runs = "".join(
        f"<li><a href='/analysis-runs/{run.id}'>{escape(run.feature_summary)}</a><span>{escape(status_label(run.status, language))} - {escape(task_type_label(run.task_type, language))}</span></li>"
        for run in runs
        if run.project_id == project.id
    ) or f"<li class='empty'>{escape('No analysis requests for this project yet.' if language == 'en' else 'Запросов анализа для проекта пока нет.')}</li>"
    source = project.repository_url or project.archive_reference or "n/a"
    return render_page(
        title=project.name,
        current_path="/projects",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(project.source_type)}</p>
            <h2>{escape(project.name)}</h2>
            <p class="lead">{escape(project.description or project.ingestion_note)}</p>
          </div>
          <a class="button-link" href="/analysis-runs/new?project_id={project.id}">{escape(t("new_analysis", language))}</a>
        </header>
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("source", language))}</h3></div>
            <dl class="meta-grid">
              <dt>{escape(t("reference", language))}</dt><dd><code>{escape(source)}</code></dd>
              <dt>{escape(t("ingestion", language))}</dt><dd>{escape(project.ingestion_status)}</dd>
              <dt>{escape(t("boundary", language))}</dt><dd>{escape(project.ingestion_note)}</dd>
              <dt>{escape(t("created", language))}</dt><dd>{_format_dt(project.created_at)}</dd>
            </dl>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("analysis_requests", language))}</h3></div>
            <ul class="link-list">{project_runs}</ul>
          </article>
        </section>
        """,
    )


def render_documents_page(documents: list[DocumentListItem], *, error: str | None = None, language: str = "en") -> str:
    rows = "".join(
        f"""
        <tr>
          <td><a href="/documents/{document.id}">{escape(document.filename)}</a></td>
          <td>{escape(document.kind)}</td>
          <td>{document.chunk_count}</td>
          <td>{_format_dt(document.created_at)}</td>
        </tr>
        """
        for document in documents
    ) or f"<tr><td colspan='4' class='empty'>{escape(t('no_documents', language))}</td></tr>"
    return render_page(
        title=t("documents", language),
        current_path="/documents",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(t("documents", language))}</p>
            <h2>{escape(t("upload_sources", language))}</h2>
          </div>
        </header>
        {_flash(error, tone='error') if error else ''}
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("upload_document", language))}</h3></div>
            <form method="post" action="/documents/upload" enctype="multipart/form-data" class="stack-form">
              <label>{escape(t("document_kind", language))}<input type="text" name="kind" value="specification" required></label>
              <label>{escape(t("source_file", language))}<input type="file" name="file" accept=".txt,.md" required></label>
              <button type="submit">{escape(t("upload", language))}</button>
            </form>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("stored_documents", language))}</h3></div>
            <table>
              <thead><tr><th>Filename</th><th>{escape(t("document_kind", language))}</th><th>Chunks</th><th>{escape(t("created", language))}</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </article>
        </section>
        """,
    )


def render_document_detail(document: DocumentDetail, runs: list[AnalysisRunListItem], *, language: str = "en") -> str:
    chunks = "".join(
        f"""
        <article class="subpanel">
          <h4>Chunk {chunk.chunk_index}</h4>
          <p class="mono">Tokens: {chunk.token_estimate}</p>
          <pre>{escape(chunk.text)}</pre>
        </article>
        """
        for chunk in document.chunks
    )
    document_runs = "".join(
        f"<li><a href='/analysis-runs/{run.id}'>{escape(run.feature_summary)}</a>{_review_badge(run.review_status)}</li>"
        for run in runs
        if run.document_id == document.id
    ) or f"<li class='empty'>{escape('No analysis runs for this document yet.' if language == 'en' else 'Для этого документа пока нет запросов анализа.')}</li>"
    return render_page(
        title=document.filename,
        current_path="/documents",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(document.kind)}</p>
            <h2>{escape(document.filename)}</h2>
            <p class="lead">Stored at <code>{escape(document.storage_path)}</code></p>
          </div>
          <a class="button-link" href="/analysis-runs/new?document_id={document.id}">{escape("Create analysis run" if language == "en" else t("create_analysis_run", language))}</a>
        </header>
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>Document metadata</h3></div>
            <dl class="meta-grid">
              <dt>Content type</dt><dd>{escape(document.content_type)}</dd>
              <dt>Chunk count</dt><dd>{document.chunk_count}</dd>
              <dt>Created</dt><dd>{_format_dt(document.created_at)}</dd>
            </dl>
            <h4>Associated runs</h4>
            <ul class="link-list">{document_runs}</ul>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>Extracted text</h3></div>
            <pre>{escape(document.extracted_text)}</pre>
          </article>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>Chunks</h3></div>
          <div class="stack">{chunks}</div>
        </section>
        """,
    )


def render_new_analysis_page(
    documents: list[DocumentListItem],
    projects: list[ProjectListItem],
    *,
    error: str | None = None,
    selected_document_id: str | None = None,
    selected_project_id: str | None = None,
    language: str = "en",
) -> str:
    project_options = "".join(
        f"<option value='{project.id}' {'selected' if str(project.id) == selected_project_id else ''}>{escape(project.name)}</option>"
        for project in projects
    )
    document_options = "".join(
        f"""
        <label class="checkbox-row">
          <input type="checkbox" name="document_ids" value="{document.id}" {"checked" if str(document.id) == selected_document_id else ""}>
          <span>{escape(document.filename)} <small>{escape(document.kind)}</small></span>
        </label>
        """
        for document in documents
    ) or f"<p class='empty'>{escape(t('upload_before_analysis', language))}</p>"
    return render_page(
        title=t("new_analysis", language),
        current_path="/analysis-runs/new",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(t("new_analysis", language))}</p>
            <h2>{escape(t("create_analysis_run", language))}</h2>
            <p class="lead">{escape(t("analysis_lead", language))}</p>
          </div>
        </header>
        {_flash(error, tone='error') if error else ''}
        <section class="panel">
          <form method="post" action="/analysis-runs" enctype="multipart/form-data" class="stack-form">
            <label>{escape(t("project", language))}
              <select name="project_id" required>
                <option value="">{escape(t("select_project", language))}</option>
                {project_options}
              </select>
            </label>
            <label>{escape(t("task_type", language))}
              <select name="task_type" required>
                <option value="feature">{escape(task_type_label("feature", language))}</option>
                <option value="enhancement">{escape(task_type_label("enhancement", language))}</option>
                <option value="bug">{escape(task_type_label("bug", language))}</option>
                <option value="technical_task">{escape(task_type_label("technical_task", language))}</option>
                <option value="spike">{escape(task_type_label("spike", language))}</option>
              </select>
            </label>
            <label>{escape(t("initial_input", language))}
              <textarea name="input_text" rows="4" placeholder="{escape(t("initial_input_hint", language))}"></textarea>
            </label>
            <label>{escape(t("initial_input_file", language))}
              <input type="file" name="input_file">
            </label>
            <label>{escape(t("query", language))}
              <textarea name="query" rows="4" required>{escape(t("query_default", language))}</textarea>
            </label>
            <label>{escape(t("document_kind_filter", language))}
              <input type="text" name="document_kind" placeholder="{escape(t("optional_spec", language))}">
            </label>
            <label>{escape(t("max_chunks", language))}
              <input type="number" name="max_chunks" min="1" max="20" value="6" required>
            </label>
            <fieldset>
              <legend>{escape(t("select_documents", language))}</legend>
              <div class="checkbox-list">{document_options}</div>
            </fieldset>
            <button type="submit">{escape(t("start_analysis", language))}</button>
          </form>
        </section>
        """,
    )


def render_analysis_runs_page(runs: list[AnalysisRunListItem], *, language: str = "en") -> str:
    return _render_analysis_table_page(
        runs,
        title=t("analysis_runs", language),
        eyebrow="Review Queue" if language == "en" else "Очередь ревью",
        current_path="/analysis-runs",
        cta_label="Create run" if language == "en" else "Создать запрос",
        cta_href="/analysis-runs/new",
        language=language,
    )


def _render_analysis_table_page(
    runs: list[AnalysisRunListItem],
    *,
    title: str,
    eyebrow: str,
    current_path: str,
    cta_label: str | None = None,
    cta_href: str | None = None,
    language: str = "en",
) -> str:
    rows = "".join(
        f"""
        <tr>
          <td><a href="/analysis-runs/{run.id}">{escape(run.feature_summary)}</a></td>
          <td>{escape(run.project_name or "n/a")}</td>
          <td>{escape(task_type_label(run.task_type, language))}</td>
          <td>{_status_badge(run.status, language)}</td>
          <td>{_review_badge(run.review_status, language)}</td>
          <td>{run.confidence:.2f}</td>
          <td>{_format_dt(run.created_at)}</td>
        </tr>
        """
        for run in runs
    ) or f"<tr><td colspan='7' class='empty'>{escape(t('no_analysis_runs', language))}</td></tr>"
    cta = f'<a class="button-link" href="{cta_href}">{escape(cta_label or "")}</a>' if cta_href and cta_label else ""
    return render_page(
        title=title,
        current_path=current_path,
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(eyebrow)}</p>
            <h2>{escape(title)}</h2>
          </div>
          {cta}
        </header>
        <section class="panel">
          <table>
            <thead><tr><th>{escape(t("summary", language))}</th><th>{escape(t("project", language))}</th><th>{escape(t("task_type", language))}</th><th>{escape(t("run_status", language))}</th><th>{escape(t("review_status", language))}</th><th>{escape(t("confidence", language))}</th><th>{escape(t("created", language))}</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        """,
    )


def render_clarifications_page(runs: list[AnalysisRunListItem], *, language: str = "en") -> str:
    pending = [run for run in runs if run.status in {"needs_clarification", "clarification_answered"}]
    return _render_analysis_table_page(
        pending,
        title=t("clarifications", language),
        eyebrow="Clarification Queue" if language == "en" else "Очередь уточнений",
        current_path="/clarifications",
        language=language,
    )


def render_results_page(runs: list[AnalysisRunListItem], *, language: str = "en") -> str:
    return _render_analysis_table_page(
        runs,
        title=t("results", language),
        eyebrow="Final Outputs" if language == "en" else "Финальные результаты",
        current_path="/results",
        language=language,
    )


def render_analysis_run_detail(
    run: AnalysisRunResponse,
    *,
    error: str | None = None,
    success: str | None = None,
    language: str = "en",
) -> str:
    task_sections = "".join(
        _render_task_section(label, getattr(run, section_name), language=language)
        for section_name, label in TASK_SECTIONS
    )
    review_options = "".join(
        f"<option value='{status}' {'selected' if run.review_status == status else ''}>{escape(status_label(status, language).title())}</option>"
        for status in ("draft", "reviewed", "approved", "rejected")
    )
    return render_page(
        title=f"Analysis {run.id}",
        current_path="/analysis-runs",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(t("analysis_runs", language))}</p>
            <h2>{escape(run.feature_summary)}</h2>
            <p class="lead">{escape(t("run_status", language))}: <strong>{escape(status_label(run.status, language))}</strong> - {escape(t("review_status", language))}: {_review_badge(run.review_status, language)} - {escape(t("confidence", language))}: {run.confidence:.2f}</p>
          </div>
          {f'<a class="button-link" href="/analysis-runs/{run.id}/export">{escape(t("preview_export", language))}</a>' if run.status == "completed" else ''}
        </header>
        {_flash(error, tone='error') if error else ''}
        {_flash(success, tone='success') if success else ''}
        <section class="grid detail-layout">
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("review_workflow", language))}</h3></div>
            <form method="post" action="/analysis-runs/{run.id}/review" class="stack-form">
              <label>{escape(t("review_status", language))}
                <select name="review_status">{review_options}</select>
              </label>
              <label>{escape(t("reviewer_note", language))}
                <textarea name="reviewer_note" rows="5" placeholder="Capture review guidance, blockers, or approval context.">{escape(run.reviewer_note)}</textarea>
              </label>
              <button type="submit">{escape(t("save_review", language))}</button>
            </form>
            <h4>{escape(t("validation_notes", language))}</h4>
            <p>{escape(run.validation_notes)}</p>
            <dl class="meta-grid">
              <dt>Run ID</dt><dd><code>{run.id}</code></dd>
              <dt>{escape(t("project", language))}</dt><dd>{escape(run.project_name or "n/a")}</dd>
              <dt>{escape(t("task_type", language))}</dt><dd>{escape(task_type_label(run.task_type, language))}</dd>
              <dt>Document ID</dt><dd><code>{run.document_id or "n/a"}</code></dd>
              <dt>{escape(t("created", language))}</dt><dd>{_format_dt(run.created_at)}</dd>
            </dl>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>{escape(t("structured_output", language))}</h3></div>
            {_render_string_list("Affected components" if language == "en" else "Затронутые компоненты", run.affected_components, language=language)}
            {_render_string_list("Risks" if language == "en" else "Риски", run.risks, language=language)}
            {_render_string_list("Open questions" if language == "en" else "Открытые вопросы", run.open_questions, language=language)}
            {_render_string_list("Assumptions" if language == "en" else "Предположения", run.assumptions, language=language)}
            {_render_source_refs("Source references" if language == "en" else "Ссылки на источники", run.source_references, language=language)}
          </article>
        </section>
        {_render_clarification_block(run, language=language)}
        <section class="panel">
          <div class="panel-header"><h3>{escape(t("generated_sections", language))}</h3></div>
          <div class="stack">{task_sections}</div>
        </section>
        """,
    )


def _render_clarification_block(run: AnalysisRunResponse, *, language: str = "en") -> str:
    if not run.clarification:
        return ""
    questions = _render_string_list("Clarifying questions" if language == "en" else "Уточняющие вопросы", run.clarification.clarifying_questions, language=language)
    missing = _render_string_list("Missing information" if language == "en" else "Недостающая информация", run.clarification.missing_information, language=language)
    assumptions = _render_string_list("Preliminary assumptions" if language == "en" else "Предварительные предположения", run.clarification.preliminary_assumptions, language=language)
    rounds = "".join(
        f"""
        <article class="subpanel">
          <h4>{"Round" if language == "en" else "Раунд"} {round_.round_index}</h4>
          {_render_string_list("AI questions" if language == "en" else "Вопросы AI", round_.questions, language=language)}
          <p><strong>{"User answer" if language == "en" else "Ответ пользователя"}:</strong> {escape(round_.answers or t("pending", language))}</p>
        </article>
        """
        for round_ in run.clarification_rounds
    )
    pending_form = ""
    if run.status == "needs_clarification":
        pending_form = f"""
        <form method="post" action="/analysis-runs/{run.id}/clarifications" class="stack-form">
          <label>{escape(t("your_answer", language))}
            <textarea name="answers" rows="5" required></textarea>
          </label>
          <button type="submit">{escape(t("submit_clarification", language))}</button>
        </form>
        """
    return f"""
    <section class="grid two-up">
      <article class="panel">
        <div class="panel-header"><h3>{escape(t("current_understanding", language))}</h3></div>
        <p>{escape(run.clarification.request_summary)}</p>
        {_render_string_list("Understood scope" if language == "en" else "Понятый scope", run.clarification.understood_scope, language=language)}
        {_render_string_list("Preliminary affected components" if language == "en" else "Предварительно затронутые компоненты", run.clarification.suspected_affected_components, language=language)}
        {missing}
        {questions}
        {assumptions}
        <p><strong>{"Clarification confidence" if language == "en" else "Уверенность уточнения"}:</strong> {run.clarification.confidence:.2f}</p>
      </article>
      <article class="panel">
        <div class="panel-header"><h3>{escape(t("clarification_rounds", language))}</h3></div>
        <div class="stack">{rounds or f"<p class='empty'>{escape('No clarification rounds.' if language == 'en' else 'Раундов уточнений пока нет.')}</p>"}</div>
        {pending_form}
      </article>
    </section>
    """


def render_export_preview_page(
    preview: JiraExportPreviewResponse,
    *,
    result: JiraExportResponse | None = None,
    error: str | None = None,
    language: str = "en",
) -> str:
    payload = preview.payload
    success = result.message if result else None
    confirmation_copy = (
        "Confirm export to Jira"
        if preview.export_mode == "live" and preview.export_allowed
        else "Confirm dry-run export"
    )
    return render_page(
        title="Jira Export Preview",
        current_path="/analysis-runs",
        language=language,
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Manual Jira Export</p>
            <h2>{escape(payload.summary)}</h2>
            <p class="lead">Export mode: <strong>{escape(preview.export_mode)}</strong> - Review status: {_review_badge(payload.review_status)} - Confidence: {payload.confidence:.2f}</p>
          </div>
          <a class="button-link" href="/analysis-runs/{preview.analysis_run_id}">Back to analysis run</a>
        </header>
        {_flash(error, tone='error') if error else ''}
        {_flash(success, tone='success') if success else ''}
        <section class="grid detail-layout">
          <article class="panel">
            <div class="panel-header"><h3>Preview controls</h3></div>
            <form method="get" action="/analysis-runs/{preview.analysis_run_id}/export" class="stack-form">
              <label>Project key
                <input type="text" name="project_key" value="{escape(payload.project_key)}" required>
              </label>
              <label>Issue type
                <input type="text" name="issue_type" value="{escape(payload.issue_type)}" required>
              </label>
              <button type="submit">Refresh preview</button>
            </form>
            <hr>
            <p>{escape(preview.message)}</p>
            {_render_string_list("Missing live configuration", preview.missing_configuration)}
            <form method="post" action="/analysis-runs/{preview.analysis_run_id}/export" class="stack-form">
              <input type="hidden" name="project_key" value="{escape(payload.project_key)}">
              <input type="hidden" name="issue_type" value="{escape(payload.issue_type)}">
              <label class="checkbox-row">
                <input type="checkbox" name="confirm" value="true" required>
                <span>I explicitly confirm this manual export action.</span>
              </label>
              <button type="submit" {"disabled" if not preview.export_allowed else ""}>{confirmation_copy}</button>
            </form>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>Human-readable export payload</h3></div>
            <dl class="meta-grid">
              <dt>Project</dt><dd>{escape(payload.project_key)}</dd>
              <dt>Issue type</dt><dd>{escape(payload.issue_type)}</dd>
              <dt>Review status</dt><dd>{escape(payload.review_status)}</dd>
              <dt>Reviewer note</dt><dd>{escape(payload.reviewer_note or "None")}</dd>
            </dl>
            <h4>Description</h4>
            <pre>{escape(payload.description)}</pre>
            {_render_string_list("Acceptance criteria", payload.acceptance_criteria)}
            {_render_string_list("Assumptions", payload.assumptions)}
            {_render_string_list("Open questions", payload.open_questions)}
            {_render_source_refs("Source references", payload.source_references)}
          </article>
        </section>
        <section class="panel">
          <div class="panel-header"><h3>Exact Jira payload preview</h3></div>
          <pre>{escape(str(preview.jira_payload))}</pre>
          {f"<p><strong>Issue URL:</strong> <a class='text-link' href='{escape(result.issue_url)}'>{escape(result.issue_url)}</a></p>" if result and result.issue_url else ""}
        </section>
        """,
    )


def _render_task_section(label: str, tasks: list[GeneratedTaskPayload], *, language: str = "en") -> str:
    cards = "".join(_render_task_card(task, language=language) for task in tasks) or f"<p class='empty'>{escape('No tasks generated for this section.' if language == 'en' else 'Для этой секции задачи не сгенерированы.')}</p>"
    return f"<section class='subsection'><h3>{escape(label)}</h3><div class='stack'>{cards}</div></section>"


def _render_task_card(task: GeneratedTaskPayload, *, language: str = "en") -> str:
    return f"""
    <article class="task-card">
      <h4>{escape(task.title)}</h4>
      <p>{escape(task.description)}</p>
      <dl class="meta-grid">
        <dt>{"Why needed" if language == "en" else "Зачем нужно"}</dt><dd>{escape(task.why_needed)}</dd>
        <dt>{"Component" if language == "en" else "Компонент"}</dt><dd>{escape(task.service_or_component)}</dd>
        <dt>{escape(t("confidence", language))}</dt><dd>{task.confidence:.2f}</dd>
      </dl>
      {_render_string_list("Acceptance criteria" if language == "en" else "Критерии приемки", task.acceptance_criteria, language=language)}
      {_render_string_list("Dependencies" if language == "en" else "Зависимости", task.dependencies, language=language)}
      {_render_string_list("Assumptions" if language == "en" else "Предположения", task.assumptions, language=language)}
      {_render_source_refs("Source refs" if language == "en" else "Источники", task.source_refs, language=language)}
    </article>
    """


def _render_string_list(label: str, values: list[str], *, language: str = "en") -> str:
    items = "".join(f"<li>{escape(value)}</li>" for value in values) or f"<li class='empty'>{escape(t('none', language))}</li>"
    return f"<div class='list-block'><h4>{escape(label)}</h4><ul>{items}</ul></div>"


def _render_source_refs(label: str, refs: list[SourceReference], *, language: str = "en") -> str:
    items = "".join(_render_source_ref(ref, language=language) for ref in refs) or f"<li class='empty'>{escape('No source references captured.' if language == 'en' else 'Ссылки на источники не сохранены.')}</li>"
    return f"<div class='list-block'><h4>{escape(label)}</h4><ul class='source-list'>{items}</ul></div>"


def _render_source_ref(ref: SourceReference, *, language: str = "en") -> str:
    parts = [
        f"<strong>{escape(ref.filename or 'Unknown file')}</strong>",
        f"{'Document' if language == 'en' else 'Документ'}: <code>{escape(ref.document_id or 'n/a')}</code>",
        f"{'Chunk' if language == 'en' else 'Фрагмент'}: <code>{escape(ref.chunk_id or 'n/a')}</code>",
    ]
    if ref.quote:
        parts.append(f"{'Quote' if language == 'en' else 'Цитата'}: {escape(ref.quote)}")
    if ref.rationale:
        parts.append(f"{'Rationale' if language == 'en' else 'Обоснование'}: {escape(ref.rationale)}")
    return f"<li>{'<br>'.join(parts)}</li>"


def _review_badge(status: str, language: str = "en") -> str:
    return _status_badge(status, language)


def _status_badge(status: str, language: str = "en") -> str:
    return f"<span class='badge badge-{escape(status)}'>{escape(status_label(status, language))}</span>"


def _nav_link(label: str, href: str, active: bool) -> str:
    class_name = "nav-link active" if active else "nav-link"
    return f"<a class='{class_name}' href='{href}'>{escape(label)}</a>"


def _stat_card(label: str, value: str, copy: str) -> str:
    return f"<article class='stat-card'><p>{escape(label)}</p><strong>{escape(value)}</strong><span>{escape(copy)}</span></article>"


def _flash(message: str, *, tone: str) -> str:
    return f"<div class='flash flash-{escape(tone)}'>{escape(message)}</div>"


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M")
