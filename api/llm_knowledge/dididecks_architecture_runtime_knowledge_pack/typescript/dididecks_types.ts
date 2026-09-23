export type Surface = "scroll" | "play" | "print" | "thumbnail" | "editor" | "export_pdf" | "export_pptx";

export type Deck = {
  id: string;
  workspaceId: string;
  title: string;
  deckType: "pitch_deck" | "investor_update" | "sales_deck" | "board_deck" | string;
  status: "draft" | "in_review" | "approved" | "archived" | string;
};

export type DeckSlide = {
  id: string;
  deckId: string;
  slideNumber: number;
  slideKey: string;
  title: string;
  slideType: string;
};

export type DeckSlideVariant = {
  id: string;
  deckId: string;
  slideId: string;
  variantKey: string;
  variantLabel?: string;
  componentKey?: string;
  isDefault?: boolean;
};

export type DeckBlock = {
  id: string;
  deckId: string;
  slideId: string;
  variantId?: string;
  blockKey: string;
  blockType: "text" | "image" | "shape" | "chart" | "table" | "metric" | "logo" | "icon" | "video" | "embed" | "card";
  contentJson: Record<string, unknown>;
  styleJson: Record<string, unknown>;
  positionJson: { x: number; y: number; width: number; height: number; rotation?: number };
  dataBindingKey?: string | null;
  isLocked?: boolean;
  isGenerated?: boolean;
};

export type PersistentField = {
  id: string;
  deckId: string;
  fieldKey: string;
  fieldLabel: string;
  fieldGroup: string;
  fieldType: "text" | "long_text" | "url" | "image" | "color" | "currency" | "percentage" | "number" | "json";
  valueJson: Record<string, unknown>;
  source?: "manual" | "import" | "research" | "ai" | string;
};

export type FieldUsage = {
  id: string;
  deckId: string;
  persistentFieldId: string;
  fieldKey: string;
  slideId: string;
  variantId?: string | null;
  blockId: string;
  usageType: "text_render" | "link_render" | "image_render" | "style_token" | "metric_render" | "chart_data";
  transformRule?: string | null;
  isRequired?: boolean;
};

export type DeckEditorViewModel = {
  deck: Deck;
  slides: DeckSlide[];
  activeSlide: DeckSlide;
  activeVariant: DeckSlideVariant;
  blocks: DeckBlock[];
  persistentFields: PersistentField[];
  fieldUsages: FieldUsage[];
  comments: unknown[];
  versions: unknown[];
  exports: unknown[];
};
