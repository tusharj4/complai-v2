interface StatusBadgeProps {
  status: string;
}

const statusStyles: Record<string, string> = {
  compliant: "bg-green-100 text-green-800",
  non_compliant: "bg-red-100 text-red-800",
  review_required: "bg-yellow-100 text-yellow-800",
  pending: "bg-gray-100 text-gray-800",
  at_risk: "bg-red-100 text-red-800",
  no_data: "bg-gray-100 text-gray-500",
};

const statusLabels: Record<string, string> = {
  compliant: "Compliant",
  non_compliant: "Non-Compliant",
  review_required: "Review Required",
  pending: "Pending",
  at_risk: "At Risk",
  no_data: "No Data",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const style = statusStyles[status] || "bg-gray-100 text-gray-600";
  const label = statusLabels[status] || status;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}
    >
      {label}
    </span>
  );
}
