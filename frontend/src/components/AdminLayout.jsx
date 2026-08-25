import DashboardLayout from "./DashboardLayout";

const NAV_ITEMS = [
  { to: "/admin", label: "Overview", end: true },
  { to: "/admin/visibility-gap", label: "Visibility Gap" },
  { to: "/admin/diversity", label: "Diversity Report" },
  { to: "/admin/recruiters", label: "Recruiter Bias Scores" },
];

export default function AdminLayout() {
  return <DashboardLayout navItems={NAV_ITEMS} roleLabel="Admin — Bias Audit Engine" />;
}
