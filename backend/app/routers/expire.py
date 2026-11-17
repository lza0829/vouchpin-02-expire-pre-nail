from __future__ import annotations
from typing import Any
from fastapi import APIRouter
from app.services import expire_service as svc

router = APIRouter(tags=["expire"])


@router.post("/expire/scan")
def scan(body: dict[str, Any] | None = None):
    return svc.scan_now(body or {})


@router.get("/expire/scans")
def scans():
    return svc.list_scans()


@router.get("/expire/voids")
def voids():
    return svc.list_voids()


@router.get("/expire/reconcile")
def reconcile():
    return svc.reconcile()
