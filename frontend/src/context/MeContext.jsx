import { createContext, useContext } from "react";
import { useFetch } from "@/lib/api";

const MeCtx = createContext(null);

export const ROLE_RANK = { admin: 4, gestor: 3, operador: 2, consulta: 1, pendente: 0 };

export function MeProvider({ children }) {
  const { data, loading, error, reload } = useFetch("/me");
  return <MeCtx.Provider value={{ me: data, loading, error, reload }}>{children}</MeCtx.Provider>;
}

export function useMe() {
  const { me } = useContext(MeCtx);
  const role = me?.role || "pendente";
  return {
    me,
    role,
    isAdmin: role === "admin",
    canGestao: ROLE_RANK[role] >= 3,
    canOperar: ROLE_RANK[role] >= 2,
  };
}

export const useMeState = () => useContext(MeCtx);
