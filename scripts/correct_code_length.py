from django.apps import apps

from libs.models.base_model_mixin import AutoCodeMixin


def run():
    models = apps.get_models()
    for model in models:
        if not model.__module__.startswith("apps"):
            continue

        if not issubclass(model, AutoCodeMixin):
            continue

        print("processing model:", model.__name__)
        try:
            instances_to_update = []
            for instance in model.objects.all():
                code_prefix = getattr(model, "CODE_PREFIX", "TEMP_")
                if model.__name__ == "Employee":
                    code_prefix = instance.code_type
                code_postfix = str(instance.id).zfill(9)
                correct_code = f"{code_prefix}{code_postfix}"
                instance.code = correct_code
                instances_to_update.append(instance)

            model.objects.bulk_update(instances_to_update, ["code"])
        except Exception as e:
            print(f"  Error processing model {model.__name__}: {e}")


if __name__ == "__main__":
    run()
