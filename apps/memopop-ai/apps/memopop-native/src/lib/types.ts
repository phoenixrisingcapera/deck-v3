export interface Outline {
  id: string;
  title: string;
  outline_type: string;
  type_label: string;
  description: string;
  section_count: number;
  compatible_modes: string[];
  firm: string | null;
  version: string | null;
}

export interface CreateFirmResult {
  slug: string;
  conventional_name: string;
  firm_dir: string;
  brand_config_path: string;
}

export type MemoMode = 'consider' | 'justify';
