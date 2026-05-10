export const formatActive = (isActive: number): string => (isActive === 1 ? "활성" : "비활성");

export const truncateText = (value: string | null | undefined, max = 80): string => {
  if (!value) return "-";
  return value.length > max ? `${value.slice(0, max)}...` : value;
};
