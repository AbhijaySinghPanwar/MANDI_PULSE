{# Fails for rows where the modal price is not between min and max (inclusive).
   Applies only when BOTH min and max are present (missing min/max are allowed, user
   decision 2026-10-03). Usage: - modal_between_min_max: {arguments: {modal: .., low: .., high: ..}} #}
{% test modal_between_min_max(model, modal='modal_price', low='min_price', high='max_price') %}
select *
from {{ model }}
where {{ low }} is not null
  and {{ high }} is not null
  and not ({{ low }} <= {{ modal }} and {{ modal }} <= {{ high }}) is true
{% endtest %}
