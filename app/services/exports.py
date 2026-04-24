from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis import AnalysisRunResponse
from app.schemas.export import (
    JiraExportPayload,
    JiraExportPreviewRequest,
    JiraExportPreviewResponse,
    JiraExportRequest,
    JiraExportResponse,
)
from app.services.analysis_runs import AnalysisRunService


class JiraExportError(ValueError):
    """Raised when the export flow cannot proceed safely."""


@dataclass(frozen=True)
class JiraConfigurationState:
    export_mode: str
    missing_configuration: list[str]

    @property
    def live_ready(self) -> bool:
        return self.export_mode == "live"


class JiraExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.analysis_runs = AnalysisRunService(db)

    def build_preview(self, payload: JiraExportPreviewRequest) -> JiraExportPreviewResponse:
        run = self._get_run(payload.analysis_run_id)
        config = self._configuration_state()
        export_payload = self._build_export_payload(run, payload)

        return JiraExportPreviewResponse(
            export_allowed=run.review_status == "approved",
            export_mode=config.export_mode,
            analysis_run_id=run.id,
            message=self._preview_message(run, config),
            payload=export_payload,
            jira_payload=self._jira_payload(export_payload),
            missing_configuration=config.missing_configuration,
        )

    def execute_export(self, payload: JiraExportRequest) -> JiraExportResponse:
        if not payload.confirm:
            raise JiraExportError("Explicit confirmation is required before a Jira export can proceed.")

        preview = self.build_preview(payload)
        if not preview.export_allowed:
            raise JiraExportError("Only approved analysis runs can be exported to Jira.")

        if preview.export_mode != "live":
            return JiraExportResponse(
                status="dry_run",
                export_allowed=True,
                export_mode=preview.export_mode,
                analysis_run_id=preview.analysis_run_id,
                message="Jira is not fully configured, so this export stayed in dry-run preview mode.",
                payload=preview.payload,
                jira_payload=preview.jira_payload,
                missing_configuration=preview.missing_configuration,
            )

        issue_key, issue_url = self._send_to_jira(preview.jira_payload)
        return JiraExportResponse(
            status="exported",
            export_allowed=True,
            export_mode=preview.export_mode,
            analysis_run_id=preview.analysis_run_id,
            message="The approved analysis run was exported to Jira.",
            payload=preview.payload,
            jira_payload=preview.jira_payload,
            issue_key=issue_key,
            issue_url=issue_url,
            missing_configuration=preview.missing_configuration,
        )

    def _get_run(self, analysis_run_id: UUID) -> AnalysisRunResponse:
        run = self.analysis_runs.get_run(analysis_run_id)
        if run is None:
            raise JiraExportError("Analysis run not found.")
        return run

    def _build_export_payload(
        self,
        run: AnalysisRunResponse,
        payload: JiraExportPreviewRequest,
    ) -> JiraExportPayload:
        project_key = (payload.project_key or self.settings.jira_project_key).strip() or self.settings.jira_project_key
        issue_type = (payload.issue_type or self.settings.jira_issue_type).strip() or self.settings.jira_issue_type
        acceptance_criteria = self._acceptance_criteria(run)
        description = self._description(run, project_key=project_key, issue_type=issue_type, acceptance_criteria=acceptance_criteria)

        return JiraExportPayload(
            project_key=project_key,
            issue_type=issue_type,
            summary=self._summary(run),
            description=description,
            acceptance_criteria=acceptance_criteria,
            assumptions=run.assumptions,
            open_questions=run.open_questions,
            source_references=run.source_references,
            confidence=run.confidence,
            review_status=run.review_status,
            reviewer_note=run.reviewer_note,
        )

    @staticmethod
    def _acceptance_criteria(run: AnalysisRunResponse) -> list[str]:
        criteria: list[str] = []
        for section_name in (
            "backend_tasks",
            "frontend_tasks",
            "integration_tasks",
            "db_changes",
            "qa_tasks",
            "observability_tasks",
        ):
            for task in getattr(run, section_name):
                criteria.extend(task.acceptance_criteria)
        return list(dict.fromkeys(criteria))

    def _description(
        self,
        run: AnalysisRunResponse,
        *,
        project_key: str,
        issue_type: str,
        acceptance_criteria: list[str],
    ) -> str:
        return "\n\n".join(
            section
            for section in (
                f"Project: {project_key}\nIssue Type: {issue_type}",
                f"Feature Summary\n{run.feature_summary}",
                self._bullet_section("Affected Components", run.affected_components),
                self._bullet_section("Acceptance Criteria", acceptance_criteria),
                self._bullet_section("Assumptions", run.assumptions),
                self._bullet_section("Open Questions", run.open_questions),
                self._bullet_section(
                    "Source References",
                    [
                        f"{ref.filename or 'Unknown file'} | chunk={ref.chunk_id or 'n/a'} | rationale={ref.rationale or 'n/a'}"
                        for ref in run.source_references
                    ],
                ),
                f"Confidence\n{run.confidence:.2f}",
                f"Review Status\n{run.review_status}",
                f"Reviewer Note\n{run.reviewer_note or 'None'}",
            )
            if section
        )

    @staticmethod
    def _summary(run: AnalysisRunResponse) -> str:
        summary = run.feature_summary.strip()
        return summary[:197] + "..." if len(summary) > 200 else summary

    @staticmethod
    def _bullet_section(title: str, values: list[str]) -> str:
        if not values:
            return ""
        bullets = "\n".join(f"- {value}" for value in values)
        return f"{title}\n{bullets}"

    def _jira_payload(self, payload: JiraExportPayload) -> dict[str, Any]:
        return {
            "fields": {
                "project": {"key": payload.project_key},
                "issuetype": {"name": payload.issue_type},
                "summary": payload.summary,
                "description": payload.description,
                "labels": ["ai-sa", "manual-export", f"review-{payload.review_status}"],
            },
            "metadata": {
                "confidence": payload.confidence,
                "review_status": payload.review_status,
                "reviewer_note": payload.reviewer_note,
                "acceptance_criteria": payload.acceptance_criteria,
                "assumptions": payload.assumptions,
                "open_questions": payload.open_questions,
                "source_references": [ref.model_dump(mode="json") for ref in payload.source_references],
            },
        }

    def _configuration_state(self) -> JiraConfigurationState:
        missing: list[str] = []
        if not self.settings.jira_export_enabled:
            missing.append("JIRA_EXPORT_ENABLED=true")
        if not self.settings.jira_base_url:
            missing.append("JIRA_BASE_URL")
        if not self.settings.jira_user_email:
            missing.append("JIRA_USER_EMAIL")
        if not self.settings.jira_api_token:
            missing.append("JIRA_API_TOKEN")
        return JiraConfigurationState(
            export_mode="live" if not missing else "dry_run",
            missing_configuration=missing,
        )

    @staticmethod
    def _preview_message(run: AnalysisRunResponse, config: JiraConfigurationState) -> str:
        if run.review_status != "approved":
            return "This run can be previewed, but export stays blocked until the review status is approved."
        if config.live_ready:
            return "This approved run is ready for explicit manual export confirmation."
        return "This approved run can enter export preview, but Jira is not fully configured so confirmation stays in dry-run mode."

    def _send_to_jira(self, jira_payload: dict[str, Any]) -> tuple[str, str | None]:
        issue_endpoint = self._issue_endpoint()
        encoded_credentials = base64.b64encode(
            f"{self.settings.jira_user_email}:{self.settings.jira_api_token}".encode("utf-8")
        ).decode("ascii")
        jira_request = request.Request(
            issue_endpoint,
            data=json.dumps(jira_payload).encode("utf-8"),
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(jira_request, timeout=15) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise JiraExportError(f"Jira export failed with status {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise JiraExportError(f"Jira export failed: {exc.reason}") from exc

        body = json.loads(raw_body)
        return body.get("key", "unknown"), body.get("self")

    def _issue_endpoint(self) -> str:
        base_url = (self.settings.jira_base_url or "").rstrip("/")
        return f"{base_url}/rest/api/3/issue"
