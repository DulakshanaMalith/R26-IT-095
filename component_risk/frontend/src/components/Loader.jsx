import { LoaderCircle } from "lucide-react";

export default function Loader({ label = "Loading..." }) {
  return (
    <div className="loader">
      <LoaderCircle className="spin" size={26} />
      <span>{label}</span>
    </div>
  );
}
