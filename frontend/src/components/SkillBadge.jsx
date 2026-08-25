const TIER_CLASSES = {
  Declared: "badge-declared",
  Confirmed: "badge-confirmed",
  Verified: "badge-verified",
};

const TIER_STARS = {
  Declared: "★",
  Confirmed: "★★",
  Verified: "★★★",
};

export default function SkillBadge({ skill, tier, sources }) {
  return (
    <div
      className={`badge ${TIER_CLASSES[tier] || "badge-declared"}`}
      title={sources ? `Corroborated by: ${sources.join(", ")}` : undefined}
    >
      <span>{skill}</span>
      <span className="font-mono">{TIER_STARS[tier] || "★"}</span>
    </div>
  );
}
