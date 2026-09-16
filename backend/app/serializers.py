"""Mongo document -> API dict conversion helpers."""
from __future__ import annotations

from typing import Any, Dict, Optional


def oid(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def user_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "tenant_id": oid(doc.get("tenant_id")),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "role": doc.get("role"),
        "created_at": doc.get("created_at"),
    }


def tenant_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "company_name": doc.get("company_name", ""),
        "plan_name": doc.get("plan_name", "starter"),
        "status": doc.get("status", "active"),
        "monthly_job_quota": doc.get("monthly_job_quota", 0),
        "created_at": doc.get("created_at"),
    }


def project_out(
    doc: Dict[str, Any],
    job_counts: Optional[Dict[str, int]] = None,
    lead_count: int = 0,
) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "tenant_id": oid(doc.get("tenant_id")),
        "name": doc.get("name", ""),
        "target_region": doc.get("target_region", "jakarta"),
        "description": doc.get("description"),
        "created_by": oid(doc.get("created_by")),
        "created_at": doc.get("created_at"),
        "job_counts": job_counts or {},
        "lead_count": lead_count,
    }


def job_out(doc: Dict[str, Any], project_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "project_id": oid(doc.get("project_id")),
        "project_name": project_name,
        "tenant_id": oid(doc.get("tenant_id")),
        "source_url": doc.get("source_url", ""),
        "status": doc.get("status", "pending"),
        "attempts": doc.get("attempts", 0),
        "error_message": doc.get("error_message"),
        "lead_id": oid(doc.get("lead_id")),
        "pages_crawled": doc.get("pages_crawled", 0),
        "created_at": doc.get("created_at"),
        "started_at": doc.get("started_at"),
        "completed_at": doc.get("completed_at"),
    }


def lead_out(doc: Dict[str, Any], has_redesign: bool = False) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "project_id": oid(doc.get("project_id")),
        "tenant_id": oid(doc.get("tenant_id")),
        "business_name": doc.get("business_name"),
        "website_url": doc.get("website_url", ""),
        "whatsapp_number": doc.get("whatsapp_number"),
        "phone_number": doc.get("phone_number"),
        "email": doc.get("email"),
        "address": doc.get("address"),
        "contact_person": doc.get("contact_person"),
        "region": doc.get("region"),
        "source_page": doc.get("source_page"),
        "audit_score": doc.get("audit_score"),
        "status": doc.get("status", "new"),
        "notes": doc.get("notes"),
        "tags": doc.get("tags", []),
        "field_confidence": doc.get("field_confidence", {}),
        "has_redesign": has_redesign,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def audit_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "lead_id": oid(doc.get("lead_id")),
        "score": doc.get("score", 0),
        "grade": doc.get("grade", "E"),
        "issues": doc.get("issues", []),
        "strengths": doc.get("strengths", []),
        "breakdown": doc.get("breakdown", {}),
        "redesign_summary": doc.get("redesign_summary", ""),
        "opportunity_summary": doc.get("opportunity_summary", ""),
        "created_at": doc.get("created_at"),
    }


def redesign_out(doc: Dict[str, Any], api_prefix: str) -> Dict[str, Any]:
    lead_id = oid(doc.get("lead_id"))
    return {
        "id": oid(doc["_id"]),
        "lead_id": lead_id,
        "version": doc.get("version", 1),
        "headline": doc.get("headline", ""),
        "subheadline": doc.get("subheadline", ""),
        "sections": doc.get("sections", []),
        "preview_html": doc.get("preview_html", ""),
        "download_url": f"{api_prefix}/redesign/{lead_id}/download",
        "generated_with": doc.get("generated_with", "template"),
        "created_at": doc.get("created_at"),
    }


def activity_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": oid(doc["_id"]),
        "tenant_id": oid(doc.get("tenant_id")),
        "user_id": oid(doc.get("user_id")),
        "action": doc.get("action", ""),
        "target": doc.get("target"),
        "detail": doc.get("detail"),
        "created_at": doc.get("created_at"),
    }
