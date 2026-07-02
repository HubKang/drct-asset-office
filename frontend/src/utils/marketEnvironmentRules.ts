import type { MarketIndexItem } from "@/types/marketIndex";
import type { MarketIndicator, MarketIndicatorValue } from "@/types/marketIndicator";

export type MarketEnvironmentTone = "positive" | "neutral" | "caution" | "risk";

export interface MarketEnvironmentInsight {
  key: string;
  title: string;
  tone: MarketEnvironmentTone;
  headline: string;
  description: string;
  evidence: Array<{ label: string; value: string }>;
  perspectives: Array<{ label: string; text: string }>;
  updatedAt?: string | null;
}

export interface BuildMarketEnvironmentInsightsParams {
  marketIndexes: MarketIndexItem[];
  marketIndicators: MarketIndicator[];
  marketIndicatorValues?: Record<string, MarketIndicatorValue[]>;
}

const toneLabels: Record<MarketEnvironmentTone, string> = {
  positive: "긍정",
  neutral: "중립",
  caution: "주의",
  risk: "위험",
};

export const getMarketEnvironmentToneLabel = (tone: MarketEnvironmentTone) => toneLabels[tone];

const asNumber = (value?: number | null) => (typeof value === "number" && Number.isFinite(value) ? value : null);

const formatNumber = (value?: number | null, fraction = 2) => {
  const num = asNumber(value);
  if (num === null) return "-";
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: fraction, minimumFractionDigits: fraction }).format(num);
};

const formatPercent = (value?: number | null) => {
  const num = asNumber(value);
  if (num === null) return "-";
  return (num > 0 ? "+" : "") + formatNumber(num, 2) + "%";
};

const formatSignedNumber = (value?: number | null, fraction = 3) => {
  const num = asNumber(value);
  if (num === null) return "-";
  return (num > 0 ? "+" : "") + formatNumber(num, fraction);
};

const formatBp = (value?: number | null) => {
  const num = asNumber(value);
  if (num === null) return "-";
  const bp = num * 100;
  return (bp > 0 ? "+" : "") + formatNumber(bp, 1) + "bp";
};

const indexReturn5 = (item?: MarketIndexItem | null) => asNumber(item?.recent_5d_return_pct ?? item?.recent_5d_return);
const indexReturn20 = (item?: MarketIndexItem | null) => asNumber(item?.recent_20d_return_pct ?? item?.recent_20d_return);

const indicatorNumericValue = (row?: MarketIndicatorValue | null) => asNumber(row?.value ?? row?.close_value);

const sortIndicatorValues = (rows?: MarketIndicatorValue[]) =>
  [...(rows ?? [])]
    .filter((row) => indicatorNumericValue(row) !== null && row.value_date)
    .sort((a, b) => a.value_date.localeCompare(b.value_date));

const calcChangePct = (rows?: MarketIndicatorValue[], days = 5) => {
  const sorted = sortIndicatorValues(rows);
  if (sorted.length <= days) return null;
  const latest = indicatorNumericValue(sorted[sorted.length - 1]);
  const base = indicatorNumericValue(sorted[sorted.length - 1 - days]);
  if (latest === null || base === null || base === 0) return null;
  return ((latest - base) / base) * 100;
};

const calcRateChangeBp = (rows?: MarketIndicatorValue[], days = 5) => {
  const sorted = sortIndicatorValues(rows);
  if (sorted.length <= days) return null;
  const latest = indicatorNumericValue(sorted[sorted.length - 1]);
  const base = indicatorNumericValue(sorted[sorted.length - 1 - days]);
  if (latest === null || base === null) return null;
  return (latest - base) * 100;
};

const latestIndicatorDate = (indicator?: MarketIndicator | null, rows?: MarketIndicatorValue[]) => {
  const sorted = sortIndicatorValues(rows);
  return sorted[sorted.length - 1]?.value_date || indicator?.latest_value_date || null;
};

const missingInsight = (key: string, title: string, domain: string): MarketEnvironmentInsight => ({
  key,
  title,
  tone: "neutral",
  headline: domain + " 데이터 확인 필요",
  description: "수집 데이터가 부족해 해석을 보류합니다. 지표 수집 상태를 확인한 뒤 참고해 주세요.",
  evidence: [{ label: "상태", value: "데이터 없음" }],
  perspectives: [
    { label: "확인 포인트", text: "해당 지표의 최신 수집 상태와 대체 지표를 함께 확인해야 합니다." },
  ],
});

export function buildMarketEnvironmentInsights({ marketIndexes, marketIndicators, marketIndicatorValues = {} }: BuildMarketEnvironmentInsightsParams): MarketEnvironmentInsight[] {
  const indexByCode = (code: string) => marketIndexes.find((item) => item.index_code === code);
  const indicatorByCode = (code: string) => marketIndicators.find((item) => item.indicator_code === code);
  const valuesByCode = (code: string) => marketIndicatorValues[code] ?? [];

  const kospi = indexByCode("KOSPI");
  const kosdaq = indexByCode("KOSDAQ");
  const kospi5 = indexReturn5(kospi);
  const kosdaq5 = indexReturn5(kosdaq);
  const stockInsight = (() => {
    if (kospi5 === null || kosdaq5 === null) return missingInsight("stock", "주식시장 흐름", "주식시장");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "국내 주식시장 혼조 흐름";
    let description = "코스피와 코스닥 흐름이 엇갈려 시장 전반의 방향성은 선별적으로 참고할 필요가 있습니다.";
    if (kospi5 > 0 && kosdaq5 > 0) {
      tone = "positive";
      headline = "국내 주식시장 반등 흐름";
      description = "코스피와 코스닥이 함께 상승해 시장 전반의 위험선호가 개선되는 흐름으로 참고할 수 있습니다.";
    } else if (kospi5 < 0 && kosdaq5 < 0) {
      tone = "caution";
      headline = "국내 주식시장 약세 흐름";
      description = "주요 지수가 함께 하락해 시장 전반의 투자심리가 약해진 상태로 해석할 수 있습니다.";
    } else if (kospi5 > 0 && kosdaq5 < 0) {
      tone = "caution";
      headline = "대형주 우위 흐름";
      description = "코스피가 상대적으로 강하고 코스닥이 약해 성장주·중소형주 수급은 선별적으로 볼 필요가 있습니다.";
    } else if (kospi5 < 0 && kosdaq5 > 0) {
      tone = "neutral";
      headline = "코스닥 상대 강세 흐름";
      description = "코스닥이 상대적으로 강해 성장주·테마주 수급이 일부 살아나는 흐름으로 참고할 수 있습니다.";
    }
    return {
      key: "stock",
      title: "주식시장 흐름",
      tone,
      headline,
      description,
      evidence: [
        { label: "KOSPI 5일", value: formatPercent(kospi5) },
        { label: "KOSDAQ 5일", value: formatPercent(kosdaq5) },
      ],
      perspectives: [
        { label: "긍정 관점", text: "코스닥 상대 강세는 성장주·테마주 수급 회복 가능성으로 참고할 수 있습니다." },
        { label: "주의 관점", text: "코스피 약세와 동반되면 시장 전체 체력은 약할 수 있습니다." },
        { label: "확인 포인트", text: "대형주와 코스닥의 상대 강도를 함께 확인해야 합니다." },
      ],
      updatedAt: kospi?.latest_price_date || kosdaq?.latest_price_date,
    };
  })();

  const usdKrw = indicatorByCode("USD_KRW");
  const usdChangePct = asNumber(usdKrw?.latest_change_pct);
  const fxInsight = (() => {
    if (!usdKrw || usdChangePct === null) return missingInsight("fx", "환율 환경", "환율");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "환율 변동 제한적";
    let description = "원/달러 환율 변화가 크지 않아 환율 측면의 시장 부담은 제한적으로 보입니다.";
    if (usdChangePct >= 0.3) {
      tone = "caution";
      headline = "원/달러 상승, 원화 약세 흐름";
      description = "원/달러 환율 상승은 외국인 수급 부담 요인으로 작용할 수 있어 시장환경 확인이 필요합니다.";
    } else if (usdChangePct <= -0.3) {
      tone = "positive";
      headline = "원/달러 하락, 원화 강세 흐름";
      description = "원화 강세는 외국인 수급 부담 완화 요인으로 참고할 수 있습니다.";
    }
    return {
      key: "fx",
      title: "환율 환경",
      tone,
      headline,
      description,
      evidence: [
        { label: "원/달러", value: formatNumber(usdKrw.latest_value, 2) + (usdKrw.unit_label || usdKrw.unit || "원") },
        { label: "변화", value: formatSignedNumber(usdKrw.latest_change_value, 2) },
        { label: "변화율", value: formatPercent(usdKrw.latest_change_pct) },
      ],
      perspectives: [
        { label: "주의 관점", text: "원화 약세는 외국인 수급 부담 요인으로 작용할 수 있습니다." },
        { label: "반대 관점", text: "수출기업에는 원화 환산 실적 측면에서 우호적일 수 있습니다." },
        { label: "확인 포인트", text: "환율 상승에도 반도체, 자동차, 조선 등 수출 업종이 강한지 확인해야 합니다." },
      ],
      updatedAt: usdKrw.latest_value_date,
    };
  })();

  const ktb10 = indicatorByCode("KTB_10Y");
  const ktb3 = indicatorByCode("KTB_3Y");
  const baseRate = indicatorByCode("BASE_RATE");
  const ktb10Change = asNumber(ktb10?.latest_change_value);
  const rateInsight = (() => {
    if (!ktb10 || ktb10Change === null) return missingInsight("rate", "금리 환경", "금리");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "장기금리 변동 제한적";
    let description = "장기금리 변화가 크지 않아 금리 측면의 방향성은 제한적으로 참고할 수 있습니다.";
    if (ktb10Change > 0.01) {
      tone = "caution";
      headline = "장기금리 상승, 할인율 부담 가능";
      description = "국고채 10년 금리 상승은 성장주·바이오·코스닥 등 장기 성장 기대주에 부담 요인으로 해석될 수 있습니다.";
    } else if (ktb10Change < -0.01) {
      tone = "positive";
      headline = "장기금리 하락, 부담 완화 가능";
      description = "국고채 10년 금리 하락은 할인율 부담 완화 요인으로 참고할 수 있습니다.";
    }
    return {
      key: "rate",
      title: "금리 환경",
      tone,
      headline,
      description,
      evidence: [
        { label: "국고채 10년", value: formatNumber(ktb10.latest_value, 3) + "%" },
        { label: "10년 변화", value: formatBp(ktb10.latest_change_value) },
        { label: "국고채 3년", value: ktb3 ? formatNumber(ktb3.latest_value, 3) + "%" : "-" },
        { label: "기준금리", value: baseRate ? formatNumber(baseRate.latest_value, 3) + "%" : "-" },
      ],
      perspectives: [
        { label: "긍정 관점", text: "장기금리 하락은 성장주 할인율 부담 완화 요인으로 참고할 수 있습니다." },
        { label: "주의 관점", text: "금리 하락이 경기 둔화 우려에서 나온 것이라면 경기민감주에는 부담이 될 수 있습니다." },
        { label: "확인 포인트", text: "코스닥, 바이오, 성장 업종의 상대 강도를 함께 확인해야 합니다." },
      ],
      updatedAt: ktb10.latest_value_date,
    };
  })();

  const cpi = indicatorByCode("CPI");
  const ppi = indicatorByCode("PPI");
  const cpiMom = asNumber(cpi?.latest_mom_pct);
  const cpiYoy = asNumber(cpi?.latest_yoy_pct);
  const inflationInsight = (() => {
    if (!cpi || (cpiMom === null && cpiYoy === null)) return missingInsight("inflation", "물가 환경", "물가");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "물가 흐름 확인 필요";
    let description = "소비자물가 흐름은 금리 기대와 시장 밸류에이션 부담을 함께 확인할 때 참고할 수 있습니다.";
    if ((cpiMom ?? 0) > 0 || (cpiYoy ?? 0) >= 2.5) {
      tone = "caution";
      headline = "물가 부담 확인 필요";
      description = "소비자물가 상승 흐름은 금리 인하 기대를 약화시키는 요인으로 참고할 수 있습니다.";
    } else if ((cpiMom ?? 0) < 0 || (cpiYoy !== null && cpiYoy < 2.0)) {
      tone = "positive";
      headline = "물가 부담 완화 가능성";
      description = "소비자물가 상승 압력이 둔화되면 금리 부담 완화 요인으로 해석할 수 있습니다.";
    }
    const ppiYoy = asNumber(ppi?.latest_yoy_pct);
    const ppiText = ppiYoy !== null && ppiYoy > 0 ? "생산자 비용 부담도 함께 확인이 필요합니다." : description;
    return {
      key: "inflation",
      title: "물가 환경",
      tone,
      headline,
      description: ppiYoy !== null && ppiYoy > 0 && tone !== "positive" ? ppiText : description,
      evidence: [
        { label: "CPI", value: formatNumber(cpi.latest_value, 2) },
        { label: "CPI MoM", value: formatPercent(cpi.latest_mom_pct) },
        { label: "CPI YoY", value: formatPercent(cpi.latest_yoy_pct) },
        { label: "PPI YoY", value: ppi ? formatPercent(ppi.latest_yoy_pct) : "-" },
      ],
      perspectives: [
        { label: "주의 관점", text: "CPI/PPI 상승은 금리 부담 요인으로 작용할 수 있습니다." },
        { label: "반대 관점", text: "물가 둔화는 금리 인하 기대를 높이는 요인으로 참고할 수 있습니다." },
        { label: "확인 포인트", text: "CPI YoY와 PPI YoY가 같은 방향으로 움직이는지 확인해야 합니다." },
      ],
      updatedAt: cpi.latest_value_date,
    };
  })();

  const csi = indicatorByCode("CSI");
  const bsi = indicatorByCode("BSI_MANUFACTURING");
  const csiValue = asNumber(csi?.latest_value);
  const bsiValue = asNumber(bsi?.latest_value);
  const economyInsight = (() => {
    if (csiValue === null || bsiValue === null) return missingInsight("economy", "경기 심리", "경기 심리");
    const csiBase = asNumber(csi?.base_line_value) ?? 100;
    const bsiBase = asNumber(bsi?.base_line_value) ?? 100;
    const csiStrong = csiValue >= csiBase;
    const bsiStrong = bsiValue >= bsiBase;
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "경기 심리 신호 혼재";
    let description = "소비자심리와 제조업 체감경기 신호가 엇갈려 경기 흐름은 선별적으로 참고할 필요가 있습니다.";
    if (csiStrong && bsiStrong) {
      tone = "positive";
      headline = "소비·제조 심리 기준선 상회";
      description = "소비자심리와 제조업 체감경기가 모두 기준선을 웃돌아 경기 심리는 양호한 편으로 볼 수 있습니다.";
    } else if (!csiStrong && !bsiStrong) {
      tone = "caution";
      headline = "경기 심리 기준선 하회";
      description = "소비자심리와 제조업 체감경기가 모두 기준선을 밑돌아 경기 심리 위축을 참고해야 합니다.";
    } else if (csiStrong && !bsiStrong) {
      tone = "caution";
      headline = "소비심리 양호, 제조업 체감경기 부진";
      description = "소비자심리는 기준선을 상회하지만 제조업 BSI는 기준선을 하회해 경기 신호가 엇갈립니다.";
    }
    return {
      key: "economy",
      title: "경기 심리",
      tone,
      headline,
      description,
      evidence: [
        { label: "CSI", value: formatNumber(csiValue, 1) },
        { label: "BSI", value: formatNumber(bsiValue, 1) },
        { label: "기준선", value: "100" },
      ],
      perspectives: [
        { label: "긍정 관점", text: "CSI 100 상회는 소비심리가 양호하다는 참고 신호가 될 수 있습니다." },
        { label: "주의 관점", text: "BSI 100 하회는 제조업 체감경기 부진으로 해석될 수 있습니다." },
        { label: "확인 포인트", text: "소비와 제조업 신호가 같은 방향인지 함께 확인해야 합니다." },
      ],
      updatedAt: csi?.latest_value_date || bsi?.latest_value_date,
    };
  })();

  const gold = indexByCode("GOLD_KRX");
  const gold20 = indexReturn20(gold);
  const riskInsight = (() => {
    if (gold20 === null || kospi5 === null || kosdaq5 === null) return missingInsight("risk", "위험회피 흐름", "위험회피");
    const stockWeak = kospi5 < 0 && kosdaq5 < 0;
    const stockStrong = kospi5 > 0 && kosdaq5 > 0;
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "위험회피 신호 제한적";
    let description = "금현물과 주식시장 흐름이 뚜렷하게 같은 방향으로 나타나지는 않습니다.";
    if (gold20 > 0 && stockWeak) {
      tone = "risk";
      headline = "위험회피 흐름 강화 가능성";
      description = "금현물 상승과 주식시장 약세가 함께 나타나면 위험회피 심리가 커지는 구간으로 참고할 수 있습니다.";
    } else if (gold20 < 0 && stockStrong) {
      tone = "positive";
      headline = "위험선호 회복 가능성";
      description = "금현물 약세와 주식시장 강세가 함께 나타나면 위험선호 회복 흐름으로 볼 수 있습니다.";
    }
    return {
      key: "risk",
      title: "위험회피 흐름",
      tone,
      headline,
      description,
      evidence: [
        { label: "금현물 20일", value: formatPercent(gold20) },
        { label: "KOSPI 5일", value: formatPercent(kospi5) },
        { label: "KOSDAQ 5일", value: formatPercent(kosdaq5) },
      ],
      perspectives: [
        { label: "주의 관점", text: "금현물 상승과 주식시장 약세가 함께 나타나면 위험회피 가능성을 참고할 수 있습니다." },
        { label: "반대 관점", text: "금현물 상승은 위험회피가 아니라 인플레이션 헤지 성격일 수도 있습니다." },
        { label: "확인 포인트", text: "환율, 금리, 주식시장 흐름이 동시에 위험회피를 가리키는지 확인해야 합니다." },
      ],
      updatedAt: gold?.latest_price_date || kospi?.latest_price_date,
    };
  })();



  const usNasdaq = indicatorByCode("US_NASDAQ");
  const usSp500 = indicatorByCode("US_SP500");
  const usDow = indicatorByCode("US_DOW");
  const usSox = indicatorByCode("US_SOX");
  const us10y = indicatorByCode("US_10Y");
  const us2y = indicatorByCode("US_2Y");
  const usFedFunds = indicatorByCode("US_FED_FUNDS");
  const usNasdaq5 = calcChangePct(valuesByCode("US_NASDAQ"), 5) ?? asNumber(usNasdaq?.latest_change_pct);
  const usSp5005 = calcChangePct(valuesByCode("US_SP500"), 5) ?? asNumber(usSp500?.latest_change_pct);
  const usDow5 = calcChangePct(valuesByCode("US_DOW"), 5) ?? asNumber(usDow?.latest_change_pct);
  const usSox5 = calcChangePct(valuesByCode("US_SOX"), 5) ?? asNumber(usSox?.latest_change_pct);
  const usNasdaq20 = calcChangePct(valuesByCode("US_NASDAQ"), 20);
  const usSp50020 = calcChangePct(valuesByCode("US_SP500"), 20);
  const us10y5bp = calcRateChangeBp(valuesByCode("US_10Y"), 5) ?? (asNumber(us10y?.latest_change_value) !== null ? asNumber(us10y?.latest_change_value)! * 100 : null);
  const us2yLatest = asNumber(us2y?.latest_value);
  const us10yLatest = asNumber(us10y?.latest_value);
  const usSpread = us10yLatest !== null && us2yLatest !== null ? (us10yLatest - us2yLatest) * 100 : null;
  const usFedFundsChangeBp = asNumber(usFedFunds?.latest_change_value) !== null ? asNumber(usFedFunds?.latest_change_value)! * 100 : null;

  const usMarketInsight = (() => {
    if (usNasdaq5 === null || usSp5005 === null || !usNasdaq || !usSp500) return missingInsight("us-market", "\uBBF8\uAD6D\uC2DC\uC7A5 \uD750\uB984", "\uBBF8\uAD6D\uC2DC\uC7A5");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "\uBBF8\uAD6D \uC8FC\uC694 \uC9C0\uC218 \uD750\uB984\uC774 \uC5C7\uAC08\uB9BD\uB2C8\uB2E4.";
    let description = "\uB098\uC2A4\uB2E5\uACFC S&P 500 \uD750\uB984\uC774 \uC644\uC804\uD788 \uAC19\uC740 \uBC29\uD5A5\uC740 \uC544\uB2C8\uC5B4\uC11C \uC120\uBCC4\uC801\uC73C\uB85C \uD655\uC778\uD560 \uD544\uC694\uAC00 \uC788\uC2B5\uB2C8\uB2E4.";
    if (usNasdaq5 > 0 && usSp5005 > 0) {
      tone = "positive";
      headline = "\uBBF8\uAD6D \uC131\uC7A5\uC8FC\uC640 \uB300\uD615\uC8FC \uD750\uB984\uC774 \uD568\uAED8 \uAC1C\uC120\uB418\uACE0 \uC788\uC2B5\uB2C8\uB2E4.";
      description = "\uB098\uC2A4\uB2E5\uACFC S&P 500\uC774 \uCD5C\uADFC 5\uAC70\uB798\uC77C \uAE30\uC900 \uB3D9\uBC18 \uC0C1\uC2B9\uD574 \uAE00\uB85C\uBC8C \uC704\uD5D8\uC120\uD638\uB97C \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
    } else if (usNasdaq5 < 0 && usSp5005 < 0) {
      tone = "caution";
      headline = "\uBBF8\uAD6D \uC8FC\uC694 \uC9C0\uC218 \uD750\uB984\uC774 \uC57D\uD654\uB418\uACE0 \uC788\uC2B5\uB2C8\uB2E4.";
      description = "\uB098\uC2A4\uB2E5\uACFC S&P 500\uC774 \uCD5C\uADFC 5\uAC70\uB798\uC77C \uAE30\uC900 \uB3D9\uBC18 \uC57D\uC138\uB77C\uBA74 \uAE00\uB85C\uBC8C \uC8FC\uC2DD\uC2DC\uC7A5 \uD22C\uC790\uC2EC\uB9AC \uB465\uD654\uB97C \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
    } else if ((usDow5 ?? 0) > 0 && usNasdaq5 < 0) {
      tone = "neutral";
      headline = "\uBBF8\uAD6D \uC2DC\uC7A5 \uB0B4\uC5D0\uC11C \uAC00\uCE58\uC8FC\uC640 \uC131\uC7A5\uC8FC \uD750\uB984\uC774 \uC5C7\uAC08\uB9BD\uB2C8\uB2E4.";
      description = "\uB2E4\uC6B0\uB294 \uACAC\uC870\uD558\uC9C0\uB9CC \uB098\uC2A4\uB2E5 \uD750\uB984\uC774 \uC57D\uD558\uBA74 \uC131\uC7A5\uC8FC \uC120\uD638\uAC00 \uC57D\uD574\uC9C0\uB294\uC9C0 \uD655\uC778\uC774 \uD544\uC694\uD569\uB2C8\uB2E4.";
    }
    return {
      key: "us-market",
      title: "\uBBF8\uAD6D\uC2DC\uC7A5 \uD750\uB984",
      tone,
      headline,
      description,
      evidence: [
        { label: "NASDAQ 5\uC77C", value: formatPercent(usNasdaq5) },
        { label: "S&P 500 5\uC77C", value: formatPercent(usSp5005) },
        { label: "DOW 5\uC77C", value: formatPercent(usDow5) },
        { label: "NASDAQ 20\uC77C", value: formatPercent(usNasdaq20) },
        { label: "S&P 500 20\uC77C", value: formatPercent(usSp50020) },
      ],
      perspectives: [
        { label: "\uCC38\uACE0 \uAD00\uC810", text: "\uBBF8\uAD6D \uC131\uC7A5\uC8FC \uD750\uB984\uC740 \uAD6D\uB0B4 \uC131\uC7A5\uC8FC\u00B7\uAE30\uC220\uC8FC \uC2EC\uB9AC\uC5D0\uB3C4 \uC6B0\uD638\uC801\uC778 \uCC38\uACE0 \uC2E0\uD638\uAC00 \uB420 \uC218 \uC788\uC2B5\uB2C8\uB2E4." },
        { label: "\uC8FC\uC758 \uAD00\uC810", text: "\uAD6D\uB0B4 \uC218\uAE09, \uD658\uC728, \uAE08\uB9AC \uBC29\uD5A5\uACFC \uD568\uAED8 \uD655\uC778\uD574\uC57C \uD569\uB2C8\uB2E4." },
        { label: "\uD655\uC778 \uD3EC\uC778\uD2B8", text: "5\uAC70\uB798\uC77C \uD750\uB984\uC774 \uB2E8\uAE30 \uC870\uC815\uC778\uC9C0, 20\uAC70\uB798\uC77C \uD750\uB984\uACFC \uAC19\uC774 \uD655\uC778\uD574\uC57C \uD569\uB2C8\uB2E4." },
      ],
      updatedAt: latestIndicatorDate(usSp500, valuesByCode("US_SP500")) || latestIndicatorDate(usNasdaq, valuesByCode("US_NASDAQ")),
    };
  })();

  const usSemiconductorInsight = (() => {
    if (usSox5 === null || !usSox) return missingInsight("us-semiconductor", "\uAE00\uB85C\uBC8C \uBC18\uB3C4\uCCB4 \uC2EC\uB9AC", "\uAE00\uB85C\uBC8C \uBC18\uB3C4\uCCB4");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "\uAE00\uB85C\uBC8C \uBC18\uB3C4\uCCB4 \uD750\uB984\uC744 \uD655\uC778\uD560 \uAD6C\uAC04\uC785\uB2C8\uB2E4.";
    let description = "\uD544\uB77C\uB378\uD53C\uC544 \uBC18\uB3C4\uCCB4\uC9C0\uC218\uC758 \uB2E8\uAE30 \uD750\uB984\uC744 \uAD6D\uB0B4 \uBC18\uB3C4\uCCB4 \uAD00\uB828 \uC218\uAE09\uACFC \uD568\uAED8 \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
    if (usSox5 >= 3) {
      tone = "positive";
      headline = "\uBBF8\uAD6D \uBC18\uB3C4\uCCB4 \uC9C0\uC218 \uD750\uB984\uC774 \uAC15\uD569\uB2C8\uB2E4.";
      description = "\uD544\uB77C\uB378\uD53C\uC544 \uBC18\uB3C4\uCCB4\uC9C0\uC218\uAC00 \uCD5C\uADFC 5\uAC70\uB798\uC77C \uAE30\uC900 \uAC15\uC138\uB77C\uBA74 \uAD6D\uB0B4 \uBC18\uB3C4\uCCB4 \uD14C\uB9C8 \uC2EC\uB9AC\uC5D0 \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
    } else if (usSox5 <= -3) {
      tone = "caution";
      headline = "\uBBF8\uAD6D \uBC18\uB3C4\uCCB4 \uC9C0\uC218 \uD750\uB984\uC774 \uC57D\uD569\uB2C8\uB2E4.";
      description = "\uD544\uB77C\uB378\uD53C\uC544 \uBC18\uB3C4\uCCB4\uC9C0\uC218 \uC57D\uC138\uB294 \uAD6D\uB0B4 \uBC18\uB3C4\uCCB4 \uD14C\uB9C8\uC758 \uB2E8\uAE30 \uC218\uAE09 \uBD80\uB2F4 \uC5EC\uBD80\uB97C \uD655\uC778\uD560 \uC2E0\uD638\uB85C \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
    } else if ((usNasdaq5 ?? 0) > 0 && usSox5 > 0) {
      tone = "positive";
      headline = "\uBBF8\uAD6D \uAE30\uC220\uC8FC\uC640 \uBC18\uB3C4\uCCB4 \uC2EC\uB9AC\uAC00 \uD568\uAED8 \uAC1C\uC120\uB418\uACE0 \uC788\uC2B5\uB2C8\uB2E4.";
    } else if ((usNasdaq5 ?? 0) > 0 && usSox5 < 0) {
      tone = "neutral";
      headline = "\uAE30\uC220\uC8FC \uC804\uCCB4\uC640 \uBC18\uB3C4\uCCB4 \uD750\uB984\uC774 \uC5C7\uAC08\uB9BD\uB2C8\uB2E4.";
    }
    return {
      key: "us-semiconductor",
      title: "\uAE00\uB85C\uBC8C \uBC18\uB3C4\uCCB4 \uC2EC\uB9AC",
      tone,
      headline,
      description,
      evidence: [
        { label: "SOX 5\uC77C", value: formatPercent(usSox5) },
        { label: "NASDAQ 5\uC77C", value: formatPercent(usNasdaq5) },
        { label: "SOX \uCD5C\uC2E0", value: formatNumber(usSox.latest_value, 2) },
      ],
      perspectives: [
        { label: "\uCC38\uACE0 \uAD00\uC810", text: "\uAD6D\uB0B4 \uBC18\uB3C4\uCCB4\u00B7AI\uBC18\uB3C4\uCCB4\u00B7HBM \uAD00\uB828 \uD14C\uB9C8 \uC2EC\uB9AC\uC5D0\uB3C4 \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4." },
        { label: "\uC8FC\uC758 \uAD00\uC810", text: "\uAC1C\uBCC4 \uC885\uBAA9 \uC7AC\uB8CC\uAC00 \uAC15\uD55C \uACBD\uC6B0 \uC9C0\uC218\uC640 \uB2E4\uB974\uAC8C \uC6C0\uC9C1\uC77C \uC218 \uC788\uC2B5\uB2C8\uB2E4." },
        { label: "\uD655\uC778 \uD3EC\uC778\uD2B8", text: "\uAD6D\uB0B4 \uD14C\uB9C8 \uC218\uAE09\uC774 \uB3D9\uBC18\uB418\uB294\uC9C0 \uC2DC\uC7A5\uD2B8\uB80C\uB4DC \uBD84\uC11D\uC5D0\uC11C \uBCC4\uB3C4\uB85C \uD655\uC778\uD574\uC57C \uD569\uB2C8\uB2E4." },
      ],
      updatedAt: latestIndicatorDate(usSox, valuesByCode("US_SOX")),
    };
  })();

  const usRateInsight = (() => {
    if (us10y5bp === null || !us10y) return missingInsight("us-rate", "\uBBF8\uAD6D \uAE08\uB9AC \uD658\uACBD", "\uBBF8\uAD6D \uAE08\uB9AC");
    let tone: MarketEnvironmentTone = "neutral";
    let headline = "\uBBF8\uAD6D \uC7A5\uAE30\uAE08\uB9AC \uBCC0\uB3D9\uC740 \uC81C\uD55C\uC801\uC785\uB2C8\uB2E4.";
    let description = "\uBBF8\uAD6D 10\uB144 \uAD6D\uCC44\uAE08\uB9AC \uBCC0\uD654\uAC00 \uD06C\uC9C0 \uC54A\uC544 \uAE00\uB85C\uBC8C \uAE08\uB9AC \uBD80\uB2F4\uC740 \uC120\uBCC4\uC801\uC73C\uB85C \uCC38\uACE0\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
    if (us10y5bp >= 10) {
      tone = "caution";
      headline = "\uBBF8\uAD6D \uC7A5\uAE30\uAE08\uB9AC\uAC00 \uC0C1\uC2B9\uD558\uBA70 \uC131\uC7A5\uC8FC \uBD80\uB2F4\uC774 \uCEE4\uC9C8 \uC218 \uC788\uC2B5\uB2C8\uB2E4.";
      description = "\uBBF8\uAD6D 10\uB144 \uAD6D\uCC44\uAE08\uB9AC \uC0C1\uC2B9\uC740 \uB098\uC2A4\uB2E5\u00B7\uCF54\uC2A4\uB2E5\u00B7\uBC14\uC774\uC624\u00B7\uC131\uC7A5\uC8FC \uD750\uB984\uACFC \uD568\uAED8 \uD655\uC778\uD560 \uD544\uC694\uAC00 \uC788\uC2B5\uB2C8\uB2E4.";
    } else if (us10y5bp <= -10) {
      tone = "positive";
      headline = "\uBBF8\uAD6D \uC7A5\uAE30\uAE08\uB9AC \uBD80\uB2F4\uC774 \uC644\uD654\uB418\uACE0 \uC788\uC2B5\uB2C8\uB2E4.";
      description = "\uBBF8\uAD6D 10\uB144 \uAD6D\uCC44\uAE08\uB9AC \uD558\uB77D\uC740 \uC131\uC7A5\uC8FC \uD560\uC778\uC728 \uBD80\uB2F4 \uC644\uD654\uB85C \uD574\uC11D\uD560 \uC218 \uC788\uC9C0\uB9CC, \uACBD\uAE30 \uB465\uD654 \uC6B0\uB824\uC5D0\uC11C \uB098\uC628 \uD558\uB77D\uC778\uC9C0 \uD568\uAED8 \uD655\uC778\uD574\uC57C \uD569\uB2C8\uB2E4.";
    } else if (usSpread !== null && usSpread < 0) {
      tone = "caution";
      headline = "\uBBF8\uAD6D \uC7A5\uB2E8\uAE30 \uAE08\uB9AC\uCC28\uAC00 \uC5ED\uC804 \uC0C1\uD0DC\uC785\uB2C8\uB2E4.";
      description = "\uBBF8\uAD6D 10\uB144 \uAE08\uB9AC\uAC00 2\uB144 \uAE08\uB9AC\uBCF4\uB2E4 \uB0AE\uC740 \uAD6C\uAC04\uC740 \uACBD\uAE30 \uB465\uD654 \uC6B0\uB824\uC640 \uD568\uAED8 \uD574\uC11D\uD560 \uD544\uC694\uAC00 \uC788\uC2B5\uB2C8\uB2E4.";
    }
    return {
      key: "us-rate",
      title: "\uBBF8\uAD6D \uAE08\uB9AC \uD658\uACBD",
      tone,
      headline,
      description,
      evidence: [
        { label: "US 10Y", value: formatNumber(us10y.latest_value, 2) + "%" },
        { label: "10Y 5\uC77C", value: (us10y5bp > 0 ? "+" : "") + formatNumber(us10y5bp, 1) + "bp" },
        { label: "10Y-2Y", value: usSpread === null ? "-" : (usSpread > 0 ? "+" : "") + formatNumber(usSpread, 1) + "bp" },
        { label: "Fed Funds", value: usFedFunds ? formatNumber(usFedFunds.latest_value, 2) + "%" : "-" },
        { label: "Fed Funds \uBCC0\uD654", value: usFedFundsChangeBp === null ? "-" : (usFedFundsChangeBp > 0 ? "+" : "") + formatNumber(usFedFundsChangeBp, 1) + "bp" },
      ],
      perspectives: [
        { label: "\uC8FC\uC758 \uAD00\uC810", text: "\uBBF8\uAD6D \uAE08\uB9AC \uC0C1\uC2B9\uC740 \uAE00\uB85C\uBC8C \uC131\uC7A5\uC8FC\uC758 \uD560\uC778\uC728 \uBD80\uB2F4\uC73C\uB85C \uC791\uC6A9\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4." },
        { label: "\uBC18\uB300 \uAD00\uC810", text: "\uAE08\uB9AC \uD558\uB77D\uC740 \uBD80\uB2F4 \uC644\uD654\uC77C \uC218 \uC788\uC9C0\uB9CC \uACBD\uAE30 \uB465\uD654 \uC6B0\uB824\uC640 \uD568\uAED8 \uD574\uC11D\uD574\uC57C \uD569\uB2C8\uB2E4." },
        { label: "\uD655\uC778 \uD3EC\uC778\uD2B8", text: "\uB098\uC2A4\uB2E5, \uCF54\uC2A4\uB2E5, \uBC14\uC774\uC624, \uC131\uC7A5 \uC5C5\uC885 \uC0C1\uB300\uAC15\uB3C4\uB97C \uD568\uAED8 \uD655\uC778\uD574\uC57C \uD569\uB2C8\uB2E4." },
      ],
      updatedAt: latestIndicatorDate(us10y, valuesByCode("US_10Y")) || latestIndicatorDate(us2y, valuesByCode("US_2Y")) || latestIndicatorDate(usFedFunds, valuesByCode("US_FED_FUNDS")),
    };
  })();

  return [stockInsight, fxInsight, rateInsight, inflationInsight, economyInsight, riskInsight, usMarketInsight, usSemiconductorInsight, usRateInsight];
}
