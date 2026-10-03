import { describe, expect, it } from "vitest";
import { assess, formatFact, places } from "../src/data/mock";
import { emptyConstraints } from "../src/data/types";
describe("Dopasowanie demonstracyjne", () => {
  it("nie potwierdza dopasowania bez określenia potrzeb", () =>
    expect(assess(places[0], emptyConstraints).status).toBe("uncertain"));
  it("rozróżnia zero, false i brak danych", () => {
    const c = {
      ...emptyConstraints,
      max_steps: 0,
      require_accessible_toilet: false,
    };
    expect(assess(places[2], c).status).toBe("meets_requirements");
    expect(
      formatFact(places[0].facts.find((f) => f.attribute === "steps_count")!),
    ).toBe("Brak stopni");
    expect(
      formatFact(
        places[0].facts.find((f) => f.attribute === "elevator_available")!,
      ),
    ).toBe("Nie");
  });
  it.each(["cafe-lisboa", "muzeum", "park"])(
    "nie traktuje niepotwierdzonych danych jako dostępności: %s",
    (id) => {
      const p = places.find((p) => p.id === id)!;
      expect(
        assess(p, { ...emptyConstraints, require_accessible_toilet: true })
          .status,
      ).toBe("uncertain");
    },
  );
  it("wykrywa potwierdzone naruszenie ograniczenia", () =>
    expect(
      assess(places[0], { ...emptyConstraints, min_entrance_width_cm: 110 })
        .status,
    ).toBe("does_not_meet_requirements"));
  it("daje dopasowanie tylko dla wszystkich spełnionych wymagań", () =>
    expect(
      assess(places[0], {
        ...emptyConstraints,
        require_step_free_access: true,
        require_accessible_toilet: true,
        allowed_surfaces: ["paved"],
      }).status,
    ).toBe("meets_requirements"));
});
