import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  "https://maffqoqbjcoxaqritqol.supabase.co",
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1hZmZxb3FiamNveGFxcml0cW9sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwMjg1MTksImV4cCI6MjA5MDYwNDUxOX0.WqmsgOZLpWbbvtEVdB6VkkiOmecfgXOHPqNZlBslEXk"
);
