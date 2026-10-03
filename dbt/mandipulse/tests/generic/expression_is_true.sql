{# Fails for rows where `expression` is not true (NULL counts as failure).
   Works at model level or column level (column_name is accepted but not needed). #}
{% test expression_is_true(model, expression, column_name=none) %}
select * from {{ model }} where not ({{ expression }}) is true
{% endtest %}
