import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface ComingSoonPageProps {
  title: string;
  milestone: string;
  description: string;
}

export function ComingSoonPage({ title, milestone, description }: ComingSoonPageProps) {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-6">
      <Card className="max-w-md text-center">
        <CardHeader>
          <div className="flex justify-center mb-2">
            <Badge variant="outline">{milestone} Roadmap Target</Badge>
          </div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground mb-4">
            This module interface is scheduled for subsequent implementation according to the
            Release 1.0 Roadmap.
          </p>
          <Button variant="outline" size="sm" onClick={() => navigate("/overview")}>
            Return to Overview
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
