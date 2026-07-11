from fastapi import APIRouter, Depends, Response, status

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.flows import (
    CreateFlowRequest,
    FlowPayload,
    flow_from_payload,
    flow_payload,
)

router = APIRouter(prefix="/projects/{project_id}/flows", tags=["flows"])


@router.get("", response_model=list[FlowPayload])
async def list_flows(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> list[FlowPayload]:
    return [flow_payload(flow) for flow in container.flows.list(project_id)]


@router.post("", response_model=FlowPayload, status_code=201)
async def create_flow(
    project_id: str,
    payload: CreateFlowRequest,
    container: AppContainer = Depends(get_container),
) -> FlowPayload:
    flow = await container.flows.create(project_id, name=payload.name)
    return flow_payload(flow)


@router.get("/{flow_id}", response_model=FlowPayload)
async def get_flow(
    project_id: str,
    flow_id: str,
    container: AppContainer = Depends(get_container),
) -> FlowPayload:
    return flow_payload(container.flows.get(project_id, flow_id))


@router.put("/{flow_id}", response_model=FlowPayload)
async def save_flow(
    project_id: str,
    flow_id: str,
    payload: FlowPayload,
    container: AppContainer = Depends(get_container),
) -> FlowPayload:
    flow = await container.flows.save(project_id, flow_id, flow_from_payload(payload))
    return flow_payload(flow)


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    project_id: str,
    flow_id: str,
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.flows.delete(project_id, flow_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

