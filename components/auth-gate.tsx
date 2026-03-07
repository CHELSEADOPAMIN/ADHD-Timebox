"use client";

import React from "react";
import { ClerkProvider } from "@clerk/nextjs";
type AuthGateProps = {
  children: React.ReactNode;
};

// AuthGate is a client component so we can render the ClerkProvider
// on the client and therefore avoid server-side `headers()` calls that
// conflict with static export.
export function AuthGate({ children }: AuthGateProps) {
  return <ClerkProvider>{children}</ClerkProvider>;
}
