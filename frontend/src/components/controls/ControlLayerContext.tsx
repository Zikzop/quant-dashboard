"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { ControlContext } from "./useControlContext";

const ControlLayerContext = createContext<ControlContext>({});

export function ControlLayerProvider({
  value,
  children,
}: {
  value: ControlContext;
  children: ReactNode;
}) {
  return (
    <ControlLayerContext.Provider value={value}>
      {children}
    </ControlLayerContext.Provider>
  );
}

export function useControlLayerContext(): ControlContext {
  return useContext(ControlLayerContext);
}
