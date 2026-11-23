import { useNavigate, useLocation } from "react-router-dom";
import { Compass } from "lucide-react";
import { EmptyState } from "../components/ui/EmptyState";
import { Button } from "../components/ui/Button";

export function NotFoundPage() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <EmptyState
        icon={<Compass className="h-8 w-8 text-primary" />}
        title="404 — Page Not Found"
        description={`The requested route '${location.pathname}' does not exist or has been disabled.`}
        action={
          <Button variant="default" onClick={() => navigate("/overview")}>
            Return to Overview
          </Button>
        }
      />
    </div>
  );
}
