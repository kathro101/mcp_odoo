"""XML-RPC wrapper for Odoo communication.

The SINGLE module that talks to Odoo.  All other modules go through this.
No `xmlrpc.client` imports anywhere else in the codebase.

All methods return either:
- The raw Odoo result (list, dict, int) on success
- A structured error dict `{"status": "error", "message": "..."}` on failure
"""

from __future__ import annotations

import xmlrpc.client


class OdooClient:
    """Thin wrapper around Odoo's XML-RPC API.

    Handles authentication and provides convenience methods for common
    operations.  All errors are caught and returned as structured dicts —
    never raised.
    """

    def __init__(self, url: str, database: str, username: str, api_key: str):
        self.url = url
        self.database = database
        self.username = username
        self.api_key = api_key
        self._uid: int | None = None
        self._common: xmlrpc.client.ServerProxy | None = None
        self._object: xmlrpc.client.ServerProxy | None = None

    def _authenticate(self) -> None:
        """Lazy authentication — only connects when needed."""
        if self._uid is not None:
            return

        try:
            self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
            self._object = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
            # Odoo 16+ requires user_agent_env as 4th positional arg,
            # Odoo <16 rejects it with a Fault. Try both.
            try:
                self._uid = self._common.authenticate(
                    self.database, self.username, self.api_key, {}
                )
            except xmlrpc.client.Fault:
                self._uid = self._common.authenticate(
                    self.database,
                    self.username,
                    self.api_key,
                )
            # Odoo 17+ with API keys returns bool instead of int uid
            if isinstance(self._uid, bool):
                self._uid = 1  # API key auth, uid not needed
        except (ConnectionRefusedError, OSError) as exc:
            raise ConnectionRefusedError(f"Cannot connect to Odoo at {self.url}: {exc}") from exc

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list,
        kwargs: dict | None = None,
    ) -> list | dict | int | bool:
        """Execute an arbitrary Odoo model method via execute_kw."""
        if not model:
            return {"status": "error", "message": "Model name is required"}

        try:
            self._authenticate()
            return self._object.execute_kw(  # type: ignore[union-attr]
                self.database,
                self._uid,
                self.api_key,
                model,
                method,
                args,
                kwargs or {},
            )
        except xmlrpc.client.Fault as exc:
            return {"status": "error", "message": str(exc)}
        except ConnectionRefusedError as exc:
            return {"status": "error", "message": str(exc)}
        except OSError as exc:
            return {"status": "error", "message": str(exc)}

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str] | None = None,
        limit: int = 0,
        offset: int = 0,
        order: str = "",
    ) -> list[dict]:
        """Convenience wrapper for search + read in one call.

        Args:
            model: Odoo model technical name.
            domain: Odoo domain filter list.
            fields: List of field names to return (None = all).
            limit: Max records to return (0 = unlimited).
            offset: Number of records to skip.
            order: Sort order string (e.g. 'name ASC').

        Returns:
            List of dicts with record data, or error dict on failure.
        """
        kwargs: dict = {}
        if fields is not None:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order

        return self.execute_kw(model, "search_read", [domain], kwargs)

    def search(self, model: str, domain: list, limit: int = 0) -> list[int]:
        """Search for record IDs matching a domain.

        Args:
            model: Odoo model technical name.
            domain: Odoo domain filter list.
            limit: Max records to return (0 = unlimited).

        Returns:
            List of matching record IDs, or error dict on failure.
        """
        kwargs = {}
        if limit:
            kwargs["limit"] = limit
        return self.execute_kw(model, "search", [domain], kwargs)

    def fields_get(self, model: str, attributes: list[str] | None = None) -> dict[str, dict]:
        """Get field metadata for a model.

        Args:
            model: Odoo model technical name.
            attributes: Field attributes to fetch (None = all).

        Returns:
            Dict mapping field names to metadata dicts, or error dict on failure.
        """
        kwargs = {}
        if attributes is not None:
            kwargs["attributes"] = attributes
        return self.execute_kw(model, "fields_get", [], kwargs)
