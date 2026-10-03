{# Great-circle distance in km between two lat/lon points (mean Earth radius 6371.0088 km);
   same formula as src/mandipulse/geo/distance.py. #}
{% macro haversine_km(lat1, lon1, lat2, lon2) -%}
    (2 * 6371.0088 * asin(sqrt(
        power(sin(radians({{ lat2 }} - {{ lat1 }}) / 2), 2)
        + cos(radians({{ lat1 }})) * cos(radians({{ lat2 }}))
          * power(sin(radians({{ lon2 }} - {{ lon1 }}) / 2), 2)
    )))
{%- endmacro %}
