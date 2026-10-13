import { Navigate, useParams } from "react-router-dom";

export default function SupervisorWorkspace() {
  const { studentId } = useParams();
  return <Navigate to={studentId ? `/students/${studentId}/analyze` : "/students"} replace />;
}
