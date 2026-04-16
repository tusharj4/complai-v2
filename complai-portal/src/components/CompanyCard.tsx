import Link from "next/link";
import StatusBadge from "./StatusBadge";

interface Company {
  id: string;
  name: string;
  gst_id: string;
  created_at: string;
}

export default function CompanyCard({ company }: { company: Company }) {
  return (
    <Link href={`/companies/${company.id}`}>
      <div className="border border-gray-200 rounded-lg p-5 hover:shadow-md hover:border-indigo-300 transition cursor-pointer bg-white">
        <h3 className="font-semibold text-gray-900 text-lg">{company.name}</h3>
        <p className="text-sm text-gray-500 mt-1 font-mono">{company.gst_id}</p>
        <p className="text-xs text-gray-400 mt-3">
          Added {new Date(company.created_at).toLocaleDateString()}
        </p>
      </div>
    </Link>
  );
}
