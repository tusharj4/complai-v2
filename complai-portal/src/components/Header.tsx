"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";

export default function Header() {
  const { logout } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <Link href="/companies" className="text-xl font-bold text-indigo-600">
          CompLai
        </Link>
        <nav className="flex gap-6">
          <Link
            href="/companies"
            className="text-sm font-medium text-gray-600 hover:text-gray-900"
          >
            Companies
          </Link>
        </nav>
      </div>
      <button
        onClick={logout}
        className="text-sm text-gray-500 hover:text-red-600 transition"
      >
        Logout
      </button>
    </header>
  );
}
