import DashboardLayout from "./DashboardLayout";

const NAV_ITEMS = [
  { to: "/candidate", label: "Dashboard", end: true },
  { to: "/candidate/profile", label: "Profile Builder" },
  { to: "/candidate/competency", label: "Competency Profile" },
  { to: "/candidate/jobs", label: "Browse Jobs" },
  { to: "/candidate/applications", label: "Applications" },
  { to: "/candidate/interview-prep", label: "Interview Prep" },
  { to: "/candidate/messages", label: "Messages" },
];

export default function CandidateLayout() {
  return <DashboardLayout navItems={NAV_ITEMS} roleLabel="Candidate" />;
}
