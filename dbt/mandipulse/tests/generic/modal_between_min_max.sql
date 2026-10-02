{# Fails for rows where the modal price is not between min and max (inclusive).
   Usage (model level):  - modal_between_min_max: {modal: modal_price, low: min_price, high: max_price} #}
{% test modal_between_min_max(model, modal='modal_price', low='min_price', high='max_price') %}
select *
from {{ model }}
where not ({{ low }} <= {{ modal }} and {{ modal }} <= {{ high }}) is true
{% endtest %}
