import DashboardLayout from "./DashboardLayout";

const NAV_ITEMS = [
  { to: "/recruiter", label: "Dashboard", end: true },
  { to: "/recruiter/company", label: "Company Profile" },
  { to: "/recruiter/jobs", label: "My Jobs" },
  { to: "/recruiter/jobs/new", label: "Post a Job" },
  { to: "/recruiter/talent-pool", label: "Talent Pool" },
  { to: "/recruiter/messages", label: "Messages" },
];

export default function RecruiterLayout() {
  return <DashboardLayout navItems={NAV_ITEMS} roleLabel="Recruiter" />;
}
