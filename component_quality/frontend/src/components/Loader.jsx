import { LoaderCircle } from "lucide-react";

export default function Loader({ label = "Loading real backend data..." }) {
  return (
    <div className="loader-card">
      <LoaderCircle className="spin" size={20} />
      <span>{label}</span>
    </div>
  );
}
