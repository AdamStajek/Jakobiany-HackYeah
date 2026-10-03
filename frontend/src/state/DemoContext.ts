import { createContext, useContext } from "react";
import type { Constraints, Report } from "../data/types";
export type DemoState = {
  constraints: Constraints;
  setConstraints: (c: Constraints) => void;
  saved: string[];
  toggleSave: (id: string) => void;
  reports: Report[];
  addReport: (r: Report) => void;
  user: string | null;
  setUser: (name: string | null) => void;
  progress: Record<string, string>;
  setProgress: (id: string, status: string) => void;
  notify: (message: string) => void;
};
export const Context = createContext<DemoState>(null!);
export const useDemo = () => useContext(Context);
