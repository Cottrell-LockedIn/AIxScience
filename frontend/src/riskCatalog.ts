import source from './riskCatalog.json'

export type EvidenceSource = { title: string; url: string; finding: string; caveat: string }
export type RiskGuide = {
  id: string; title: string; features: string[]; supporting?: string[]; owners: string[]; sources: string[]
  requires: string; action: string; caveat: string
}

export const evidenceSources = source.sources as Record<string, EvidenceSource>
export const ownerNames = source.owners as Record<string, string>
export const riskCatalog = source.patterns as RiskGuide[]
