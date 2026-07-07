"""GraphQL surface — a Strawberry query layer over the same services the /api/v1 REST
contract uses (contract-first parity). Token-authed and tenant-aware, mounted at /graphql."""

from app.api.graphql.schema import build_graphql_router

__all__ = ["build_graphql_router"]
