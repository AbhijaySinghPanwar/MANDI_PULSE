{# Use the configured schema name as-is (staging, intermediate, marts, reference)
   instead of dbt's default "<target_schema>_<custom_schema>".
   Models tagged 'analysis' get var('analysis_schema_suffix') appended, so the Phase 3
   sensitivity build (include_suspect_low=true) lands in e.g. marts_incl_suspect without
   duplicating any upstream model. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set base = target.schema if custom_schema_name is none else custom_schema_name | trim -%}
    {%- if 'analysis' in node.tags -%}{{ base ~ var('analysis_schema_suffix', '') }}{%- else -%}{{ base }}{%- endif -%}
{%- endmacro %}
