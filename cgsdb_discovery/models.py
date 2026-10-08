"""Filename: cgsdb_discovery/models.py"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from typing import Any

NON_ALNUM = re.compile(r"[^a-z0-9]+")

PROVENANCE_CLASSES = {
    "official-authorized",
    "authorized-source-release",
    "leak",
    "archival-recovery",
    "reverse-engineered",
    "fan-maintained",
    "unknown",
}
LEAK_STATUSES = {
    "not-leak",
    "reported",
    "suspected",
    "confirmed",
    "historical-confirmed",
    "unknown",
}
ACCESS_STATUSES = {
    "public",
    "restricted",
    "removed",
    "private",
    "dead-link",
    "unknown",
}
REDISTRIBUTION_STATUSES = {
    "allowed",
    "restricted",
    "forbidden",
    "unknown",
}


def game_key(title: str) -> str:
    return NON_ALNUM.sub("-", title.casefold()).strip("-") or "game"


def stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(" ".join(str(p or "").split()).casefold() for p in parts)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


@dataclass(slots=True)
class EvidenceRecord:
    candidate_id: str
    evidence_source: str
    evidence_url: str
    evidence_title: str = ""
    accessed_at: str = ""
    evidence_type: str = "discovery"
    publisher_or_owner: str = ""
    source_release_date: str = ""
    license_claim: str = ""
    source_scope_claim: str = ""
    authorization_signal: str = ""
    source_completeness_claim: str = ""
    provenance_class_claim: str = "unknown"
    leak_status_claim: str = "unknown"
    content_type_claim: str = ""
    access_status_claim: str = "unknown"
    redistribution_status_claim: str = "unknown"
    classification_tags: list[str] = field(default_factory=list)
    confidence: str = "low"
    notes: str = ""

    @property
    def evidence_id(self) -> str:
        return stable_id(
            "ev",
            self.candidate_id,
            self.evidence_source,
            self.evidence_url,
            self.source_release_date,
            self.license_claim,
            self.source_scope_claim,
            self.authorization_signal,
            self.source_completeness_claim,
            self.provenance_class_claim,
            self.leak_status_claim,
            self.content_type_claim,
            self.access_status_claim,
            self.redistribution_status_claim,
            ";".join(sorted(set(self.classification_tags))),
        )

    def fingerprint(self) -> str:
        return stable_id(
            "fp",
            self.candidate_id,
            self.evidence_source,
            self.evidence_url,
            self.source_release_date,
            self.license_claim,
            self.source_scope_claim,
            self.authorization_signal,
            self.source_completeness_claim,
            self.provenance_class_claim,
            self.leak_status_claim,
            self.content_type_claim,
            self.access_status_claim,
            self.redistribution_status_claim,
            ";".join(sorted(set(self.classification_tags))),
        ).removeprefix("fp-")


@dataclass(slots=True)
class CandidateRecord:
    candidate_title: str
    developer: str = ""
    original_year: str = ""
    game_key: str = ""
    linked_game_status: str = "unresolved"
    discovery_sources: list[str] = field(default_factory=list)
    first_discovered_at: str = ""
    discovery_query: str = ""
    discovery_url: str = ""
    review_status: str = "new"
    exact_license: str = ""
    license_family: str = ""
    source_completeness: str = "unknown"
    authorization_status: str = "unknown"
    provenance_class: str = "unknown"
    leak_status: str = "not-leak"
    content_types: list[str] = field(default_factory=list)
    access_status: str = "unknown"
    redistribution_status: str = "unknown"
    classification_tags: list[str] = field(default_factory=list)
    provenance_confidence: str = "low"
    evidence_confidence: str = "low"
    notes: str = ""
    evidence: list[EvidenceRecord] = field(default_factory=list)

    @property
    def candidate_id(self) -> str:
        # Candidate identity is title/game-key based so the same game converges
        # across GitHub, Internet Archive, SteamDB, IGDB and Wayback discoveries.
        return f"cand-{self.game_key or game_key(self.candidate_title)}"

    def normalize(self) -> None:
        self.game_key = self.game_key or game_key(self.candidate_title)
        self.discovery_sources = sorted(set(x.strip() for x in self.discovery_sources if x and x.strip()))
        self.discovery_sources = self.discovery_sources or ["unknown"]
        if self.provenance_class not in PROVENANCE_CLASSES:
            self.provenance_class = "unknown"
        if self.leak_status not in LEAK_STATUSES:
            self.leak_status = "unknown"
        if self.access_status not in ACCESS_STATUSES:
            self.access_status = "unknown"
        if self.redistribution_status not in REDISTRIBUTION_STATUSES:
            self.redistribution_status = "unknown"
        self.content_types = sorted({x.strip() for x in self.content_types if x and x.strip()})
        self.classification_tags = sorted({x.strip() for x in self.classification_tags if x and x.strip()})

    def to_json(self) -> dict[str, Any]:
        self.normalize()
        data = asdict(self)
        data["candidate_id"] = self.candidate_id
        data["evidence"] = [
            {**asdict(ev), "evidence_id": ev.evidence_id, "evidence_fingerprint": ev.fingerprint()}
            for ev in self.evidence
        ]
        return data


@dataclass(slots=True)
class DiscoveryRun:
    run_id: str
    started_at: str
    completed_at: str = ""
    discovery_source: str = ""
    query_or_collection: str = ""
    status: str = "running"
    candidates_found: int = 0
    candidates_added: int = 0
    notes: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def json_line(record: CandidateRecord) -> str:
    return json.dumps(record.to_json(), ensure_ascii=False, separators=(",", ":"))
