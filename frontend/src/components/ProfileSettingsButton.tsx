import { Link } from "react-router-dom";
import { useDemo } from "../state/DemoContext";

export default function ProfileSettingsButton() {
  const { profile, setConstraints, notify } = useDemo();

  return profile ? (
    <button
      type="button"
      className="button subtle"
      onClick={() => {
        setConstraints({ ...profile.constraints });
        notify("Zastosowano ustawienia z profilu.");
      }}
    >
      Użyj ustawień z profilu
    </button>
  ) : (
    <Link className="button subtle" to="/profile/setup">
      Ustaw preferencje w profilu
    </Link>
  );
}
