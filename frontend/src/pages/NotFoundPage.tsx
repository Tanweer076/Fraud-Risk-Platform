import { Link } from "react-router";
import { PageHeader } from "../components/ui";

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" description="The address doesn't match any page." />
      <Link to="/" className="font-medium text-accent-text underline">
        Go to the dashboard
      </Link>
    </>
  );
}
