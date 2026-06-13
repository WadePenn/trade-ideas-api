from fastapi import APIRouter, HTTPException

from .builders_verticals import execute_vertical
from .builders_condors import execute_iron_condor
from .builders_calendars import execute_calendar
from .builders_rolls import execute_roll

from .models import (
    VerticalRequest,
    IronCondorRequest,
    CalendarRequest,
    RollRequest,
    OrderResult,
)

router = APIRouter(prefix="/options", tags=["options"])


@router.post("/vertical", response_model=OrderResult)
def place_vertical(req: VerticalRequest):
    result = execute_vertical(req)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message or "Vertical failed risk checks")
    return result


@router.post("/iron_condor", response_model=OrderResult)
def place_iron_condor(req: IronCondorRequest):
    result = execute_iron_condor(req)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message or "Iron condor failed risk checks")
    return result


@router.post("/calendar", response_model=OrderResult)
def place_calendar(req: CalendarRequest):
    result = execute_calendar(req)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message or "Calendar failed risk checks")
    return result


@router.post("/roll", response_model=OrderResult)
def place_roll(req: RollRequest):
    result = execute_roll(req)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message or "Roll failed risk checks")
    return result
