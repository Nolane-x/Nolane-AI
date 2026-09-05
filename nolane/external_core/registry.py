from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# Compatibility bridge retained from pre-A3 External Core.
from nolane.organization.identity import *  # noqa: F401,F403

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.component_contracts import ExternalComponentManifest


MANIFEST_ADAPTER_PROTOCOL = "external-manifest-adapter-v1"
CANONICAL_REGISTRY_PROTOCOL = "external-canonical-registry-v1"
CAPABILITY_BINDING_PROTOCOL = "external-capability-binding-v1"


def _explicit(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an explicit string")
    return value


@dataclass(frozen=True, slots=True)
class ManifestAdapter:
    """Immutable binding between a canonical source identity and an A2 manifest.

    The adapter is descriptive. It cannot grant any authority represented by the
    manifest; it only proves that the declared manifest is bound to the exact
    source component identity/version supplied by the canonical adapter builder.
    """

    adapter_id: str
    source_locator: str
    source_component_id: str
    source_component_version: str
    manifest: ExternalComponentManifest
    adapter_digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": MANIFEST_ADAPTER_PROTOCOL,
            "adapter_id": self.adapter_id,
            "source_locator": self.source_locator,
            "source_component_id": self.source_component_id,
            "source_component_version": self.source_component_version,
            "manifest": self.manifest.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "adapter_digest": self.adapter_digest}

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("manifest adapter integrity validation failed") from exc
        if restored != self:
            raise ValueError("manifest adapter integrity validation failed")

    @classmethod
    def create(
        cls,
        *,
        adapter_id: str,
        source_locator: str,
        source_component_id: str,
        source_component_version: str,
        manifest: ExternalComponentManifest,
    ) -> "ManifestAdapter":
        adapter = _explicit(adapter_id, "adapter id")
        locator = _explicit(source_locator, "source locator")
        source_id = _explicit(source_component_id, "source component identity")
        source_version = _explicit(source_component_version, "source component version")
        if source_id != manifest.component_id:
            raise ValueError("adapter source identity does not match manifest identity")
        if source_version != manifest.component_version:
            raise ValueError("adapter source version does not match manifest version")
        payload = {
            "protocol": MANIFEST_ADAPTER_PROTOCOL,
            "adapter_id": adapter,
            "source_locator": locator,
            "source_component_id": source_id,
            "source_component_version": source_version,
            "manifest": manifest.to_state(),
        }
        return cls(
            adapter_id=adapter,
            source_locator=locator,
            source_component_id=source_id,
            source_component_version=source_version,
            manifest=manifest,
            adapter_digest="adapter-v1-" + canonical_digest(payload),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ManifestAdapter":
        if str(state.get("protocol", "")) != MANIFEST_ADAPTER_PROTOCOL:
            raise ValueError("manifest adapter protocol mismatch")
        manifest_state = state.get("manifest")
        if not isinstance(manifest_state, Mapping):
            raise ValueError("manifest adapter manifest must be an object")
        expected = cls.create(
            adapter_id=state.get("adapter_id", ""),  # type: ignore[arg-type]
            source_locator=state.get("source_locator", ""),  # type: ignore[arg-type]
            source_component_id=state.get("source_component_id", ""),  # type: ignore[arg-type]
            source_component_version=state.get("source_component_version", ""),  # type: ignore[arg-type]
            manifest=ExternalComponentManifest.from_state(manifest_state),
        )
        if str(state.get("adapter_digest", "")) != expected.adapter_digest:
            raise ValueError("manifest adapter digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("manifest adapter state is non-canonical or semantically drifted")
        return expected


@dataclass(frozen=True, slots=True)
class RegistryCoverageFinding:
    code: str
    source_locator: str
    component_id: str
    detail: str

    def to_state(self) -> dict[str, str]:
        return {
            "code": self.code,
            "source_locator": self.source_locator,
            "component_id": self.component_id,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class RegistryCoverageReport:
    findings: tuple[RegistryCoverageFinding, ...]

    @property
    def coherent(self) -> bool:
        return not self.findings

    def to_state(self) -> dict[str, Any]:
        return {"coherent": self.coherent, "findings": [finding.to_state() for finding in self.findings]}


@dataclass(frozen=True, slots=True)
class CanonicalComponentRegistry:
    adapters: tuple[ManifestAdapter, ...]
    registry_digest: str

    @classmethod
    def create(cls, adapters: tuple[ManifestAdapter, ...]) -> "CanonicalComponentRegistry":
        raw_rows = tuple(adapters)
        validated_rows: list[ManifestAdapter] = []
        for row in raw_rows:
            if not isinstance(row, ManifestAdapter):
                raise ValueError("canonical registry entry must be a ManifestAdapter")
            try:
                row.validate_integrity()
            except ValueError as exc:
                raise ValueError("manifest adapter integrity invalid for canonical registry") from exc
            validated_rows.append(row)
        rows = tuple(validated_rows)
        component_ids = [row.source_component_id for row in rows]
        adapter_ids = [row.adapter_id for row in rows]
        locators = [row.source_locator for row in rows]
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("duplicate component identity in canonical registry")
        if len(set(adapter_ids)) != len(adapter_ids):
            raise ValueError("duplicate adapter identity in canonical registry")
        if len(set(locators)) != len(locators):
            raise ValueError("duplicate source locator in canonical registry")
        ordered = tuple(sorted(rows, key=lambda row: (row.source_component_id, row.adapter_id, row.source_locator)))
        payload = {
            "protocol": CANONICAL_REGISTRY_PROTOCOL,
            "adapters": [row.to_state() for row in ordered],
        }
        return cls(adapters=ordered, registry_digest="registry-v1-" + canonical_digest(payload))

    @property
    def component_ids(self) -> tuple[str, ...]:
        self.validate_integrity()
        return tuple(row.source_component_id for row in self.adapters)

    @property
    def manifests(self) -> tuple[ExternalComponentManifest, ...]:
        self.validate_integrity()
        return tuple(row.manifest for row in self.adapters)

    @property
    def component_versions(self) -> dict[str, str]:
        self.validate_integrity()
        return {row.source_component_id: row.source_component_version for row in self.adapters}

    def manifest_for(self, component_id: str) -> ExternalComponentManifest:
        self.validate_integrity()
        target = _explicit(component_id, "component id")
        for row in self.adapters:
            if row.source_component_id == target:
                return row.manifest
        raise KeyError(target)

    def adapter_for(self, component_id: str) -> ManifestAdapter:
        self.validate_integrity()
        target = _explicit(component_id, "component id")
        for row in self.adapters:
            if row.source_component_id == target:
                return row
        raise KeyError(target)

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": CANONICAL_REGISTRY_PROTOCOL,
            "adapters": [row.to_state() for row in self.adapters],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "registry_digest": self.registry_digest}

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("canonical registry integrity validation failed") from exc
        if restored != self:
            raise ValueError("canonical registry integrity validation failed")

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CanonicalComponentRegistry":
        if str(state.get("protocol", "")) != CANONICAL_REGISTRY_PROTOCOL:
            raise ValueError("canonical registry protocol mismatch")
        raw_adapters = state.get("adapters")
        if not isinstance(raw_adapters, list):
            raise ValueError("canonical registry adapters must be an array")
        adapters = tuple(
            ManifestAdapter.from_state(row) if isinstance(row, Mapping) else _invalid_adapter_state()
            for row in raw_adapters
        )
        expected = cls.create(adapters)
        if str(state.get("registry_digest", "")) != expected.registry_digest:
            raise ValueError("canonical registry digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("canonical registry state is non-canonical or semantically drifted")
        return expected

    def validate_coverage(
        self,
        expected_sources: Mapping[str, tuple[str, str]],
        *,
        reject_unexpected: bool = False,
    ) -> RegistryCoverageReport:
        self.validate_integrity()
        actual = {row.source_locator: row for row in self.adapters}
        findings: list[RegistryCoverageFinding] = []
        for locator, identity_version in sorted(expected_sources.items(), key=lambda item: str(item[0])):
            source_locator = _explicit(locator, "expected source locator")
            if not isinstance(identity_version, tuple) or len(identity_version) != 2:
                raise ValueError("coverage expectation must be (component_id, component_version)")
            expected_id = _explicit(identity_version[0], "expected component identity")
            expected_version = _explicit(identity_version[1], "expected component version")
            adapter = actual.get(source_locator)
            if adapter is None:
                findings.append(
                    RegistryCoverageFinding(
                        code="MISSING_ADAPTER",
                        source_locator=source_locator,
                        component_id=expected_id,
                        detail="canonical source has no manifest adapter",
                    )
                )
                continue
            if adapter.source_component_id != expected_id:
                findings.append(
                    RegistryCoverageFinding(
                        code="IDENTITY_DRIFT",
                        source_locator=source_locator,
                        component_id=adapter.source_component_id,
                        detail=f"expected {expected_id}",
                    )
                )
            if adapter.source_component_version != expected_version:
                findings.append(
                    RegistryCoverageFinding(
                        code="VERSION_DRIFT",
                        source_locator=source_locator,
                        component_id=adapter.source_component_id,
                        detail=f"expected {expected_version}; got {adapter.source_component_version}",
                    )
                )
        if reject_unexpected:
            for locator, adapter in sorted(actual.items()):
                if locator not in expected_sources:
                    findings.append(
                        RegistryCoverageFinding(
                            code="ORPHAN_ADAPTER",
                            source_locator=locator,
                            component_id=adapter.source_component_id,
                            detail="adapter has no canonical source expectation",
                        )
                    )
        ordered = tuple(
            sorted(findings, key=lambda row: (row.code, row.source_locator, row.component_id, row.detail))
        )
        return RegistryCoverageReport(findings=ordered)


@dataclass(frozen=True, slots=True)
class CapabilityCatalogBindingReceipt:
    catalog_version: str
    catalog_digest: str
    registry_digest: str
    descriptive_only: bool
    receipt_id: str

    @classmethod
    def create(
        cls,
        *,
        catalog_version: str,
        catalog_digest: str,
        registry_digest: str,
    ) -> "CapabilityCatalogBindingReceipt":
        version = _explicit(catalog_version, "capability catalog version")
        catalog = _explicit(catalog_digest, "capability catalog digest")
        registry = _explicit(registry_digest, "canonical registry digest")
        payload = {
            "protocol": CAPABILITY_BINDING_PROTOCOL,
            "catalog_version": version,
            "catalog_digest": catalog,
            "registry_digest": registry,
            "descriptive_only": True,
        }
        return cls(
            catalog_version=version,
            catalog_digest=catalog,
            registry_digest=registry,
            descriptive_only=True,
            receipt_id="capability-binding-v1-" + canonical_digest(payload),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": CAPABILITY_BINDING_PROTOCOL,
            "catalog_version": self.catalog_version,
            "catalog_digest": self.catalog_digest,
            "registry_digest": self.registry_digest,
            "descriptive_only": self.descriptive_only,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_id": self.receipt_id}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CapabilityCatalogBindingReceipt":
        if str(state.get("protocol", "")) != CAPABILITY_BINDING_PROTOCOL:
            raise ValueError("capability catalog binding protocol mismatch")
        if state.get("descriptive_only") is not True:
            raise ValueError("capability catalog binding must remain descriptive-only")
        expected = cls.create(
            catalog_version=state.get("catalog_version", ""),  # type: ignore[arg-type]
            catalog_digest=state.get("catalog_digest", ""),  # type: ignore[arg-type]
            registry_digest=state.get("registry_digest", ""),  # type: ignore[arg-type]
        )
        if str(state.get("receipt_id", "")) != expected.receipt_id:
            raise ValueError("capability catalog binding digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("capability catalog binding state is non-canonical or semantically drifted")
        return expected


def _invalid_adapter_state() -> ManifestAdapter:
    raise ValueError("canonical registry adapter entry must be an object")
