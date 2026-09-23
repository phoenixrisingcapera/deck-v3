export type AiDesignScope = 'current_slide' | 'selected_slides' | 'whole_deck';

export type AiDesignPreset = 'investor_ready' | 'visual_hierarchy' | 'narrative_flow' | 'sharper_vc_version';

export interface AiDesignCommand {
  scope: AiDesignScope;
  command: string;
  preset: AiDesignPreset | null;
}
