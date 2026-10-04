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
    ).toBe("0 stopni");
    expect(
      formatFact(
        places[0].facts.find((f) => f.attribute === "elevator_available")!,
      ),
    ).toBe("Nie");
  });
  it("pokazuje dokładną liczbę stopni i opisuje dostępność wymiarów", () => {
    const fact = (
      attribute:
        | "steps_count"
        | "threshold_height_cm"
        | "kerb_height_cm"
        | "entrance_width_cm",
      value: number,
    ) => ({ ...places[0].facts[0], attribute, value });
    expect(formatFact(fact("steps_count", 1))).toBe("1 stopień");
    expect(formatFact(fact("steps_count", 4))).toBe("4 stopnie");
    expect(formatFact(fact("steps_count", 5))).toBe("5 stopni");
    expect(formatFact(fact("steps_count", 10))).toBe("10 stopni");
    expect(formatFact(fact("steps_count", 12))).toBe("12 stopni");
    expect(formatFact(fact("steps_count", 22))).toBe("22 stopnie");
    expect(formatFact(fact("threshold_height_cm", 2))).toBe(
      "Accessible for wheelchairs",
    );
    expect(formatFact(fact("threshold_height_cm", 2.1))).toBe(
      "Inaccessible for wheelchairs",
    );
    expect(formatFact(fact("kerb_height_cm", 2))).toBe(
      "Accessible for wheelchairs",
    );
    expect(formatFact(fact("entrance_width_cm", 90))).toBe(
      "Accessible for wheelchairs",
    );
    expect(formatFact(fact("entrance_width_cm", 89))).toBe(
      "Inaccessible for wheelchairs",
    );
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
