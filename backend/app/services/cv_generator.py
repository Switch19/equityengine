"""
Generates a downloadable, professionally formatted CV PDF from a
candidate's unified Competency Profile — not just their uploaded CV
text, but evidence pulled from all three pipelines (CV, GitHub,
community). This is the feature's actual value for a self-taught
candidate with no formal CV at all: EquityEngine can still produce a
presentable, exportable document from their GitHub projects and
community certifications alone.

Built with pymupdf (already in your installed packages, same tool
used for the admin bias report in Phase 7) rather than a templating/
PDF-generation library, so no new dependency is needed.
"""
import fitz

from app.models import CandidateProfile, User
from app.services.competency_engine import build_competency_profile

PAGE_MARGIN = 50
LINE_HEIGHT = 16
PAGE_BOTTOM = 780


class _PdfWriter:
    """Small stateful helper so the generation function below doesn't
    have to manually track cursor position and page-overflow on every
    call — same page-overflow-protection pattern used in the Phase 7
    admin report, extracted here since CV generation needs it more
    heavily (variable-length skills/projects/certifications lists)."""

    def __init__(self):
        self.doc = fitz.open()
        self.page = self.doc.new_page()
        self.y = PAGE_MARGIN

    def _new_page_if_needed(self, extra_lines=1):
        if self.y + extra_lines * LINE_HEIGHT > PAGE_BOTTOM:
            self.page = self.doc.new_page()
            self.y = PAGE_MARGIN

    def text(self, content, size=10, bold=False, gap_after=4, indent=0):
        self._new_page_if_needed()
        font = "hebo" if bold else "helv"  # PyMuPDF base-14 aliases; "helv-bold" is NOT valid
        self.page.insert_text((PAGE_MARGIN + indent, self.y), content, fontsize=size, fontname=font)
        self.y += LINE_HEIGHT + gap_after

    def wrapped_text(self, content, size=9, indent=0, max_chars=95, gap_after=6):
        """Naive word-wrap by character count — good enough for CV
        body text at a fixed font size, avoids pulling in a text-
        measurement dependency for exact pixel-width wrapping."""
        words = content.split()
        line = ""
        for word in words:
            # Hard-break a single word that alone exceeds max_chars
            # (e.g. a long URL) — without this, such a word would
            # either overflow the page width or (in an earlier,
            # buggy version of this function) emit a spurious empty
            # line before it.
            while len(word) > max_chars:
                if line:
                    self.text(line, size=size, indent=indent, gap_after=2)
                    line = ""
                self.text(word[:max_chars], size=size, indent=indent, gap_after=2)
                word = word[max_chars:]

            candidate_line = f"{line} {word}".strip()
            if len(candidate_line) > max_chars:
                if line:
                    self.text(line, size=size, indent=indent, gap_after=2)
                line = word
            else:
                line = candidate_line
        if line:
            self.text(line, size=size, indent=indent, gap_after=gap_after)

    def section_header(self, title):
        self._new_page_if_needed(extra_lines=2)
        self.y += 6
        self.text(title.upper(), size=12, bold=True, gap_after=2)
        self.page.draw_line((PAGE_MARGIN, self.y - 8), (545, self.y - 8), color=(0.08, 0.09, 0.23), width=0.7)
        self.y += 4

    def bytes(self):
        result = self.doc.tobytes()
        self.doc.close()
        return result


def build_optimized_cv_pdf(profile: CandidateProfile, user: User) -> bytes:
    w = _PdfWriter()

    w.text(user.full_name, size=18, bold=True, gap_after=2)
    contact_parts = [user.email]
    if profile.location:
        contact_parts.append(profile.location)
    if profile.github_username:
        contact_parts.append(f"github.com/{profile.github_username}")
    w.text("  |  ".join(contact_parts), size=9, gap_after=10)

    if profile.experience_level or profile.education_tier:
        w.section_header("Summary")
        summary_bits = []
        if profile.experience_level and profile.experience_level != "Not specified":
            summary_bits.append(profile.experience_level)
        if profile.education_tier and profile.education_tier != "Undisclosed":
            summary_bits.append(f"{profile.education_tier} background")
        if profile.bio:
            summary_bits.append(profile.bio)
        w.wrapped_text(" — ".join(summary_bits) if summary_bits else "", gap_after=10)

    competency = build_competency_profile(profile)
    if competency:
        w.section_header("Skills")
        by_tier = {"Verified": [], "Confirmed": [], "Declared": []}
        for skill, meta in competency.items():
            by_tier.setdefault(meta["tier"], []).append(skill)
        for tier in ["Verified", "Confirmed", "Declared"]:
            if by_tier[tier]:
                w.wrapped_text(f"{tier}: " + ", ".join(sorted(by_tier[tier])), gap_after=4)
        w.y += 6

    all_projects = list(profile.cv_projects or [])
    for repo in (profile.github_repos or [])[:5]:
        if repo.get("description"):
            all_projects.append({
                "title": repo.get("name", "GitHub project"),
                "description": repo["description"],
            })
    if all_projects:
        w.section_header("Projects")
        for project in all_projects[:8]:
            w.text(project.get("title", "Untitled project"), size=10, bold=True, gap_after=1)
            w.wrapped_text(project.get("description", ""), gap_after=6, indent=4)

    if profile.certifications:
        w.section_header("Certifications")
        for cert in profile.certifications:
            line = cert.get("name", "")
            if cert.get("issuer"):
                line += f" — {cert['issuer']}"
            w.text(line, size=9, gap_after=3)
        w.y += 4

    w._new_page_if_needed(extra_lines=2)
    w.y += 10
    w.text(
        "Generated by EquityEngine from CV, GitHub, and community evidence.",
        size=7, gap_after=0,
    )

    return w.bytes()
