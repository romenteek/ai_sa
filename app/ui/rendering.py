from datetime import datetime
from html import escape

from app.schemas.analysis import AnalysisRunListItem, AnalysisRunResponse, GeneratedTaskPayload, SourceReference
from app.schemas.document import DocumentDetail, DocumentListItem
from app.schemas.export import JiraExportPreviewResponse, JiraExportResponse
from app.schemas.project import ProjectListItem, ProjectResponse


TASK_SECTIONS = (
    ("backend_tasks", "Backend Tasks"),
    ("frontend_tasks", "Frontend Tasks"),
    ("integration_tasks", "Integration Tasks"),
    ("db_changes", "DB Changes"),
    ("qa_tasks", "QA Tasks"),
    ("observability_tasks", "Observability Tasks"),
)


def render_page(*, title: str, current_path: str, content: str) -> str:
    navigation = "".join(
        _nav_link(label, href, current_path == href)
        for label, href in (
            ("Projects", "/projects"),
            ("New Analysis", "/analysis-runs/new"),
            ("Clarifications", "/clarifications"),
            ("Results", "/results"),
            ("Documents", "/documents"),
            ("API Docs", "/docs"),
        )
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)} - AI System Analyst</title>
    <link rel="stylesheet" href="/static/internal.css">
  </head>
  <body>
    <div class="shell">
      <aside class="sidebar">
        <h1>AI System Analyst</h1>
        <p class="sidebar-copy">Internal review flow for grounded ingestion, structured review, and explicit Jira export preview.</p>
        <nav class="nav">{navigation}</nav>
      </aside>
      <main class="content">{content}</main>
    </div>
  </body>
</html>"""


def render_dashboard(documents: list[DocumentListItem], runs: list[AnalysisRunListItem]) -> str:
    recent_documents = "".join(
        f"<li><a href='/documents/{document.id}'>{escape(document.filename)}</a><span>{escape(document.kind)}</span></li>"
        for document in documents[:5]
    ) or "<li class='empty'>No documents uploaded yet.</li>"
    recent_runs = "".join(
        f"<li><a href='/analysis-runs/{run.id}'>{escape(run.feature_summary)}</a>{_review_badge(run.review_status)}</li>"
        for run in runs[:5]
    ) or "<li class='empty'>No analysis runs yet.</li>"
    approved_count = sum(1 for run in runs if run.review_status == "approved")
    return render_page(
        title="Dashboard",
        current_path="/",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Milestone 5</p>
            <h2>Internal Review Dashboard</h2>
            <p class="lead">Project-aware analysis now starts with clarification when the request lacks enough grounded information for final output.</p>
          </div>
        </header>
        <section class="stats-grid">
          {_stat_card("Documents", str(len(documents)), "Uploaded `.txt` and `.md` sources")}
          {_stat_card("Analysis Runs", str(len(runs)), "Persisted structured outputs")}
          {_stat_card("Approved", str(approved_count), "Runs eligible for export preview confirmation")}
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


def render_projects_page(projects: list[ProjectListItem], *, error: str | None = None) -> str:
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
    ) or "<tr><td colspan='5' class='empty'>No projects yet.</td></tr>"
    return render_page(
        title="Projects",
        current_path="/projects",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Projects</p>
            <h2>Project Sources</h2>
          </div>
        </header>
        {_flash(error, tone='error') if error else ''}
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>Create project</h3></div>
            <form method="post" action="/projects" enctype="multipart/form-data" class="stack-form">
              <label>Name<input type="text" name="name" required></label>
              <label>Description<textarea name="description" rows="3"></textarea></label>
              <label>Source type
                <select name="source_type" required>
                  <option value="github">GitHub</option>
                  <option value="archive">Uploaded archive</option>
                </select>
              </label>
              <label>Repository URL<input type="url" name="repository_url" placeholder="https://github.com/org/repo"></label>
              <label>Archive file<input type="file" name="archive" accept=".zip,.tar,.gz,.tgz"></label>
              <button type="submit">Create project</button>
            </form>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>Stored projects</h3></div>
            <table>
              <thead><tr><th>Name</th><th>Source</th><th>Ingestion</th><th>Analyses</th><th>Created</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </article>
        </section>
        """,
    )


def render_project_detail(project: ProjectResponse, runs: list[AnalysisRunListItem]) -> str:
    project_runs = "".join(
        f"<li><a href='/analysis-runs/{run.id}'>{escape(run.feature_summary)}</a><span>{escape(run.status)} - {escape(run.task_type)}</span></li>"
        for run in runs
        if run.project_id == project.id
    ) or "<li class='empty'>No analysis requests for this project yet.</li>"
    source = project.repository_url or project.archive_reference or "n/a"
    return render_page(
        title=project.name,
        current_path="/projects",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(project.source_type)}</p>
            <h2>{escape(project.name)}</h2>
            <p class="lead">{escape(project.description or project.ingestion_note)}</p>
          </div>
          <a class="button-link" href="/analysis-runs/new?project_id={project.id}">New analysis</a>
        </header>
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>Source</h3></div>
            <dl class="meta-grid">
              <dt>Reference</dt><dd><code>{escape(source)}</code></dd>
              <dt>Ingestion</dt><dd>{escape(project.ingestion_status)}</dd>
              <dt>Boundary</dt><dd>{escape(project.ingestion_note)}</dd>
              <dt>Created</dt><dd>{_format_dt(project.created_at)}</dd>
            </dl>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>Analysis requests</h3></div>
            <ul class="link-list">{project_runs}</ul>
          </article>
        </section>
        """,
    )


def render_documents_page(documents: list[DocumentListItem], *, error: str | None = None) -> str:
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
    ) or "<tr><td colspan='4' class='empty'>No uploaded documents yet.</td></tr>"
    return render_page(
        title="Documents",
        current_path="/documents",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Documents</p>
            <h2>Upload and Inspect Sources</h2>
          </div>
        </header>
        {_flash(error, tone='error') if error else ''}
        <section class="grid two-up">
          <article class="panel">
            <div class="panel-header"><h3>Upload document</h3></div>
            <form method="post" action="/documents/upload" enctype="multipart/form-data" class="stack-form">
              <label>Document kind<input type="text" name="kind" value="specification" required></label>
              <label>Source file<input type="file" name="file" accept=".txt,.md" required></label>
              <button type="submit">Upload</button>
            </form>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>Stored documents</h3></div>
            <table>
              <thead><tr><th>Filename</th><th>Kind</th><th>Chunks</th><th>Created</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </article>
        </section>
        """,
    )


def render_document_detail(document: DocumentDetail, runs: list[AnalysisRunListItem]) -> str:
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
    ) or "<li class='empty'>No analysis runs for this document yet.</li>"
    return render_page(
        title=document.filename,
        current_path="/documents",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">{escape(document.kind)}</p>
            <h2>{escape(document.filename)}</h2>
            <p class="lead">Stored at <code>{escape(document.storage_path)}</code></p>
          </div>
          <a class="button-link" href="/analysis-runs/new?document_id={document.id}">Create analysis run</a>
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
    ) or "<p class='empty'>Upload a document before starting an analysis run.</p>"
    return render_page(
        title="New Analysis",
        current_path="/analysis-runs/new",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Analysis</p>
            <h2>Create Analysis Run</h2>
            <p class="lead">This uses the existing deterministic retrieval-backed pipeline and preserves the strict response contract.</p>
          </div>
        </header>
        {_flash(error, tone='error') if error else ''}
        <section class="panel">
          <form method="post" action="/analysis-runs" enctype="multipart/form-data" class="stack-form">
            <label>Project
              <select name="project_id" required>
                <option value="">Select a project</option>
                {project_options}
              </select>
            </label>
            <label>Task type
              <select name="task_type" required>
                <option value="feature">Feature</option>
                <option value="enhancement">Enhancement/change</option>
                <option value="bug">Bug</option>
                <option value="technical_task">Technical task</option>
                <option value="spike">Spike/research</option>
              </select>
            </label>
            <label>Initial input
              <textarea name="input_text" rows="4" placeholder="Describe the request, bug, change, or research question."></textarea>
            </label>
            <label>Initial input file
              <input type="file" name="input_file">
            </label>
            <label>Query
              <textarea name="query" rows="4" required>Summarize the implementation work required by the selected documents.</textarea>
            </label>
            <label>Document kind filter
              <input type="text" name="document_kind" placeholder="Optional, e.g. specification">
            </label>
            <label>Max chunks
              <input type="number" name="max_chunks" min="1" max="20" value="6" required>
            </label>
            <fieldset>
              <legend>Select documents</legend>
              <div class="checkbox-list">{document_options}</div>
            </fieldset>
            <button type="submit">Start analysis run</button>
          </form>
        </section>
        """,
    )


def render_analysis_runs_page(runs: list[AnalysisRunListItem]) -> str:
    return _render_analysis_table_page(
        runs,
        title="Analysis Runs",
        eyebrow="Review Queue",
        current_path="/analysis-runs",
        cta_label="Create run",
        cta_href="/analysis-runs/new",
    )


def _render_analysis_table_page(
    runs: list[AnalysisRunListItem],
    *,
    title: str,
    eyebrow: str,
    current_path: str,
    cta_label: str | None = None,
    cta_href: str | None = None,
) -> str:
    rows = "".join(
        f"""
        <tr>
          <td><a href="/analysis-runs/{run.id}">{escape(run.feature_summary)}</a></td>
          <td>{escape(run.project_name or "n/a")}</td>
          <td>{escape(run.task_type)}</td>
          <td>{escape(run.status)}</td>
          <td>{_review_badge(run.review_status)}</td>
          <td>{run.confidence:.2f}</td>
          <td>{_format_dt(run.created_at)}</td>
        </tr>
        """
        for run in runs
    ) or "<tr><td colspan='7' class='empty'>No analysis runs yet.</td></tr>"
    cta = f'<a class="button-link" href="{cta_href}">{escape(cta_label or "")}</a>' if cta_href and cta_label else ""
    return render_page(
        title=title,
        current_path=current_path,
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
            <thead><tr><th>Summary</th><th>Project</th><th>Task type</th><th>Run status</th><th>Review status</th><th>Confidence</th><th>Created</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        """,
    )


def render_clarifications_page(runs: list[AnalysisRunListItem]) -> str:
    pending = [run for run in runs if run.status in {"needs_clarification", "clarification_answered"}]
    return _render_analysis_table_page(
        pending,
        title="Clarifications",
        eyebrow="Clarification Queue",
        current_path="/clarifications",
    )


def render_results_page(runs: list[AnalysisRunListItem]) -> str:
    return _render_analysis_table_page(
        runs,
        title="Results",
        eyebrow="Final Outputs",
        current_path="/results",
    )


def render_analysis_run_detail(
    run: AnalysisRunResponse,
    *,
    error: str | None = None,
    success: str | None = None,
) -> str:
    task_sections = "".join(
        _render_task_section(label, getattr(run, section_name))
        for section_name, label in TASK_SECTIONS
    )
    review_options = "".join(
        f"<option value='{status}' {'selected' if run.review_status == status else ''}>{status.title()}</option>"
        for status in ("draft", "reviewed", "approved", "rejected")
    )
    return render_page(
        title=f"Analysis {run.id}",
        current_path="/analysis-runs",
        content=f"""
        <header class="page-header">
          <div>
            <p class="eyebrow">Analysis Run</p>
            <h2>{escape(run.feature_summary)}</h2>
            <p class="lead">Run status: <strong>{escape(run.status)}</strong> - Review status: {_review_badge(run.review_status)} - Confidence: {run.confidence:.2f}</p>
          </div>
          {f'<a class="button-link" href="/analysis-runs/{run.id}/export">Preview Jira export</a>' if run.status == "completed" else ''}
        </header>
        {_flash(error, tone='error') if error else ''}
        {_flash(success, tone='success') if success else ''}
        <section class="grid detail-layout">
          <article class="panel">
            <div class="panel-header"><h3>Review workflow</h3></div>
            <form method="post" action="/analysis-runs/{run.id}/review" class="stack-form">
              <label>Review status
                <select name="review_status">{review_options}</select>
              </label>
              <label>Reviewer note
                <textarea name="reviewer_note" rows="5" placeholder="Capture review guidance, blockers, or approval context.">{escape(run.reviewer_note)}</textarea>
              </label>
              <button type="submit">Save review decision</button>
            </form>
            <h4>Validation notes</h4>
            <p>{escape(run.validation_notes)}</p>
            <dl class="meta-grid">
              <dt>Run ID</dt><dd><code>{run.id}</code></dd>
              <dt>Project</dt><dd>{escape(run.project_name or "n/a")}</dd>
              <dt>Task type</dt><dd>{escape(run.task_type)}</dd>
              <dt>Document ID</dt><dd><code>{run.document_id or "n/a"}</code></dd>
              <dt>Created</dt><dd>{_format_dt(run.created_at)}</dd>
            </dl>
          </article>
          <article class="panel">
            <div class="panel-header"><h3>Structured review output</h3></div>
            {_render_string_list("Affected components", run.affected_components)}
            {_render_string_list("Risks", run.risks)}
            {_render_string_list("Open questions", run.open_questions)}
            {_render_string_list("Assumptions", run.assumptions)}
            {_render_source_refs("Source references", run.source_references)}
          </article>
        </section>
        {_render_clarification_block(run)}
        <section class="panel">
          <div class="panel-header"><h3>Generated task sections</h3></div>
          <div class="stack">{task_sections}</div>
        </section>
        """,
    )


def _render_clarification_block(run: AnalysisRunResponse) -> str:
    if not run.clarification:
        return ""
    questions = _render_string_list("Clarifying questions", run.clarification.clarifying_questions)
    missing = _render_string_list("Missing information", run.clarification.missing_information)
    assumptions = _render_string_list("Preliminary assumptions", run.clarification.preliminary_assumptions)
    rounds = "".join(
        f"""
        <article class="subpanel">
          <h4>Round {round_.round_index}</h4>
          {_render_string_list("AI questions", round_.questions)}
          <p><strong>User answer:</strong> {escape(round_.answers or "Pending")}</p>
        </article>
        """
        for round_ in run.clarification_rounds
    )
    pending_form = ""
    if run.status == "needs_clarification":
        pending_form = f"""
        <form method="post" action="/analysis-runs/{run.id}/clarifications" class="stack-form">
          <label>Your clarification answer
            <textarea name="answers" rows="5" required></textarea>
          </label>
          <button type="submit">Submit clarification</button>
        </form>
        """
    return f"""
    <section class="grid two-up">
      <article class="panel">
        <div class="panel-header"><h3>Current understanding</h3></div>
        <p>{escape(run.clarification.request_summary)}</p>
        {_render_string_list("Understood scope", run.clarification.understood_scope)}
        {_render_string_list("Preliminary affected components", run.clarification.suspected_affected_components)}
        {missing}
        {questions}
        {assumptions}
        <p><strong>Clarification confidence:</strong> {run.clarification.confidence:.2f}</p>
      </article>
      <article class="panel">
        <div class="panel-header"><h3>Clarification rounds</h3></div>
        <div class="stack">{rounds or "<p class='empty'>No clarification rounds.</p>"}</div>
        {pending_form}
      </article>
    </section>
    """


def render_export_preview_page(
    preview: JiraExportPreviewResponse,
    *,
    result: JiraExportResponse | None = None,
    error: str | None = None,
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


def _render_task_section(label: str, tasks: list[GeneratedTaskPayload]) -> str:
    cards = "".join(_render_task_card(task) for task in tasks) or "<p class='empty'>No tasks generated for this section.</p>"
    return f"<section class='subsection'><h3>{escape(label)}</h3><div class='stack'>{cards}</div></section>"


def _render_task_card(task: GeneratedTaskPayload) -> str:
    return f"""
    <article class="task-card">
      <h4>{escape(task.title)}</h4>
      <p>{escape(task.description)}</p>
      <dl class="meta-grid">
        <dt>Why needed</dt><dd>{escape(task.why_needed)}</dd>
        <dt>Component</dt><dd>{escape(task.service_or_component)}</dd>
        <dt>Confidence</dt><dd>{task.confidence:.2f}</dd>
      </dl>
      {_render_string_list("Acceptance criteria", task.acceptance_criteria)}
      {_render_string_list("Dependencies", task.dependencies)}
      {_render_string_list("Assumptions", task.assumptions)}
      {_render_source_refs("Source refs", task.source_refs)}
    </article>
    """


def _render_string_list(label: str, values: list[str]) -> str:
    items = "".join(f"<li>{escape(value)}</li>" for value in values) or "<li class='empty'>None</li>"
    return f"<div class='list-block'><h4>{escape(label)}</h4><ul>{items}</ul></div>"


def _render_source_refs(label: str, refs: list[SourceReference]) -> str:
    items = "".join(_render_source_ref(ref) for ref in refs) or "<li class='empty'>No source references captured.</li>"
    return f"<div class='list-block'><h4>{escape(label)}</h4><ul class='source-list'>{items}</ul></div>"


def _render_source_ref(ref: SourceReference) -> str:
    parts = [
        f"<strong>{escape(ref.filename or 'Unknown file')}</strong>",
        f"Document: <code>{escape(ref.document_id or 'n/a')}</code>",
        f"Chunk: <code>{escape(ref.chunk_id or 'n/a')}</code>",
    ]
    if ref.quote:
        parts.append(f"Quote: {escape(ref.quote)}")
    if ref.rationale:
        parts.append(f"Rationale: {escape(ref.rationale)}")
    return f"<li>{'<br>'.join(parts)}</li>"


def _review_badge(status: str) -> str:
    return f"<span class='badge badge-{escape(status)}'>{escape(status)}</span>"


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
