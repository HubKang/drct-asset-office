import type { AdvisoryPackageGenerateRequest, AdvisoryPackageGenerateResponse } from "@/types/advisoryPackage";

export const advisoryPackageMockRepository = {
  async generate(payload: AdvisoryPackageGenerateRequest): Promise<AdvisoryPackageGenerateResponse> {
    const now = new Date().toISOString();
    const title =
      payload.package_type === "swing"
        ? "# DrCT에셋 GPT 스윙투자 자문 패키지"
        : "# DrCT에셋 GPT 장기투자 자문 패키지";
    return {
      id: 1,
      stock_id: payload.stock_id,
      title: payload.title,
      report_type: payload.package_type === "swing" ? "gpt_swing_advisory_package" : "gpt_long_term_advisory_package",
      package_type: payload.package_type,
      markdown_content: `${title}\n\n## 1. 사용자 목표\n- 사용자가 입력한 검토 목적: ${payload.purpose}\n`,
      created_at: now,
    };
  },
};
