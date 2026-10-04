import { createContext, useContext } from "react";
import type { Constraints, Report } from "../data/types";
import type { Session, Profile, MissionActivity } from "../data/api";
export type DemoState = {
  location: { lat: number; lon: number } | null;
  setLocation: (location: { lat: number; lon: number } | null) => void;
  constraints: Constraints;
  setConstraints: (c: Constraints) => void;
  saved: string[];
  toggleSave: (id: string) => Promise<void>;
  reports: Report[];
  addReport: (r: Report) => void;
  user: string | null;
  session: Session | null;
  profile: Profile | null;
  authenticate: (
    email: string,
    password: string,
    name?: string,
  ) => Promise<void>;
  signOut: () => Promise<void>;
  saveProfile: (description: string, constraints: Constraints) => Promise<void>;
  activity: MissionActivity;
  refreshActivity: () => Promise<void>;
  notify: (message: string) => void;
};
export const Context = createContext<DemoState>(null!);
export const useDemo = () => useContext(Context);
