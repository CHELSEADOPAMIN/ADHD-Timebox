"use client";

import React from "react";
type AuthGateProps = {
  children: React.ReactNode;
};

export function AuthGate({ children }: AuthGateProps) {
  return (
    <>
      {children}
    </>
  );
}
