import { useDemo } from "../state/DemoContext";
import type { Constraints } from "../data/types";

export default function ProfileSettingsButton({
  onApply,
}: {
  onApply: (constraints: Constraints) => void;
}) {
  const { profile } = useDemo();

  return (
    <button
      type="button"
      className="button subtle"
      disabled={!profile}
      title={!profile ? "Najpierw zapisz preferencje w profilu" : undefined}
      onClick={() => {
        if (profile) onApply({ ...profile.constraints });
      }}
    >
      Ustaw preferencje z profilu
    </button>
  );
}
