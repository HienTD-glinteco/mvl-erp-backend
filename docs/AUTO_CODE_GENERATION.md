# Auto-Generated Code Logic Refactoring

## Overview

This document describes the refactored auto-generated code logic for Django models in the MVL ERP Backend project.

## Problem Statement

Previously, the codebase had significant code duplication for auto-generating the 'code' field across multiple models:
- 4 nearly identical signal handlers in `apps/hrm/signals.py` (Branch, Block, Department, RecruitmentChannel)
- Duplicate temporary code logic in model save methods
- Inconsistent approach in `apps/core/api/serializers/role.py` using sequential numbering

## Solution

A unified, reusable approach using generic signal handlers that can work with any model having a `CODE_PREFIX` attribute.

## Implementation Details

### AutoCodeMixin (libs/base_model_mixin.py)

A Django model mixin that automatically generates temporary codes for new instances.

**Features:**
- Automatically generates temporary code when creating new instances
- Configurable temporary code prefix via `TEMP_CODE_PREFIX` class attribute
- Works seamlessly with signal handlers for final code generation
- No need to override `save()` method for basic use cases

**Usage:**
```python
from libs.base_model_mixin import AutoCodeMixin, BaseModel

class Branch(AutoCodeMixin, BaseModel):
    CODE_PREFIX = "CN"
    TEMP_CODE_PREFIX = "TEMP_"  # Optional, defaults to "TEMP_"
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
```

**For models with custom save logic:**
```python
class Department(AutoCodeMixin, BaseModel):
    CODE_PREFIX = "PB"
    
    def save(self, *args, **kwargs):
        # Custom logic before temp code generation
        if not self.branch and self.block:
            self.branch = self.block.branch
        
        # Call super to handle temp code generation
        super().save(*args, **kwargs)
```

### Core Functions (libs/code_generation.py)

#### 1. `generate_model_code(instance) -> str`
Generates a code for a model instance based on its ID and class prefix.

**Format:** `{PREFIX}{subcode}`
- `subcode` is the instance ID zero-padded to at least 3 digits
- IDs >= 1000 use their full number without padding

**Example:**
```python
class Block(models.Model):
    CODE_PREFIX = "BL"
    ...

block = Block(id=1)
code = generate_model_code(block)  # Returns "BL001"

block = Block(id=1234)
code = generate_model_code(block)  # Returns "BL1234"
```

#### 2. `create_auto_code_signal_handler(temp_code_prefix: str, custom_generate_code=None)`
Factory function that creates a generic signal handler for auto-code generation.

**Parameters:**
- `temp_code_prefix`: Prefix used to identify temporary codes (e.g., "TEMP_")
- `custom_generate_code`: Optional custom function to generate codes. If provided, this function will be used instead of `generate_model_code`. The function should accept an instance and return a string code.

**Returns:** A signal handler function that can be connected to post_save signal

**Usage:**
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from libs.code_generation import create_auto_code_signal_handler

# Create generic handler with default code generation
auto_code_handler = create_auto_code_signal_handler("TEMP_")

# Create handler with custom code generation
def custom_code_gen(instance):
    return f"{instance.CODE_PREFIX}{instance.id:05d}"

custom_handler = create_auto_code_signal_handler("TEMP_", custom_generate_code=custom_code_gen)

# Register for multiple models using multiple decorators
@receiver(post_save, sender=Branch)
@receiver(post_save, sender=Block)
@receiver(post_save, sender=Department)
def generate_code(sender, instance, created, **kwargs):
    auto_code_handler(sender, instance, created, **kwargs)
```

#### 3. `register_auto_code_signal(*models, temp_code_prefix: str = "TEMP_", custom_generate_code=None)`
Convenience function to register auto-code generation for multiple models at once.

**Parameters:**
- `*models`: Model classes to register the signal for
- `temp_code_prefix`: Prefix for temporary codes (default: "TEMP_")
- `custom_generate_code`: Optional custom function to generate codes. If provided, this function will be used instead of `generate_model_code`.

**Usage:**
```python
from apps.hrm.models import Branch, Block, Department
from libs.code_generation import register_auto_code_signal

# Register with default code generation
register_auto_code_signal(Branch, Block, Department)

# Register with custom code generation
def custom_code_gen(instance):
    return f"{instance.CODE_PREFIX}{instance.id:05d}"

register_auto_code_signal(Branch, Block, custom_generate_code=custom_code_gen)
```

## How It Works

1. **Model Creation:**
   - When a model instance is created without a code, the `save()` method generates a temporary code (e.g., "TEMP_abc123xyz")
   - This temporary code ensures uniqueness before the actual ID is assigned

2. **Signal Handler Trigger:**
   - After the instance is saved and has an ID, the `post_save` signal is triggered
   - The generic handler checks:
     - Is this a newly created instance? (`created=True`)
     - Does it have a code field?
     - Does the code start with the temporary prefix?

3. **Code Generation:**
   - If all conditions are met, `generate_model_code()` is called
   - The final code is generated using the model's `CODE_PREFIX` and the instance ID
   - The instance is saved again with `update_fields=["code"]` to prevent infinite loop

## Model Requirements

For a model to use auto-code generation, it must:

1. **Inherit from `AutoCodeMixin`:**
```python
from libs.base_model_mixin import AutoCodeMixin, BaseModel

class Branch(AutoCodeMixin, BaseModel):
    CODE_PREFIX = "CN"
    ...
```

2. **Have a `CODE_PREFIX` class attribute:**
```python
CODE_PREFIX = "CN"
```

3. **Have a code field:**
```python
code = models.CharField(max_length=50, unique=True, verbose_name=_("Branch code"))
```

4. **Register the signal handler:**
```python
# In signals.py
@receiver(post_save, sender=Branch)
def generate_branch_code(sender, instance, created, **kwargs):
    auto_code_handler(sender, instance, created, **kwargs)
```

**Note:** The `AutoCodeMixin` automatically handles temporary code generation in the `save()` method, so you don't need to override it for basic use cases.

## Current Implementation (apps/hrm/signals.py)

The refactored implementation replaces 4 separate signal handlers with a single generic handler:

```python
from libs.code_generation import create_auto_code_signal_handler

# Create one handler for all models
_auto_code_handler = create_auto_code_signal_handler(TEMP_CODE_PREFIX)

# Register for all models using multiple decorators
@receiver(post_save, sender=Branch)
@receiver(post_save, sender=Block)
@receiver(post_save, sender=Department)
@receiver(post_save, sender=RecruitmentChannel)
def generate_model_code_on_save(sender, instance, created, **kwargs):
    _auto_code_handler(sender, instance, created, **kwargs)
```

**Benefits:**
- Reduced code from ~100 lines to ~15 lines
- Single source of truth for code generation logic
- Easier to maintain and extend
- Consistent behavior across all models

## Extending the System

### Adding a New Model

To add auto-code generation to a new model:

1. **Inherit from `AutoCodeMixin` and add `CODE_PREFIX`:**
```python
from libs.base_model_mixin import AutoCodeMixin, BaseModel

class NewModel(AutoCodeMixin, BaseModel):
    CODE_PREFIX = "NM"  # Choose a unique prefix
    code = models.CharField(max_length=50, unique=True)
    ...
```

2. **Register the signal handler:**
```python
# In signals.py - add to existing decorator stack
@receiver(post_save, sender=NewModel)
def generate_model_code_on_save(sender, instance, created, **kwargs):
    _auto_code_handler(sender, instance, created, **kwargs)
```

**That's it!** The `AutoCodeMixin` automatically handles temporary code generation.

### Custom Code Generation Logic

If a model needs custom code generation logic (e.g., sequential numbering like Role), you have two options:

**Option 1: Override in serializer (current Role approach)**
```python
class RoleSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        # Custom sequential logic
        last_role = Role.objects.order_by("-code").first()
        if last_role and last_role.code.startswith("VT"):
            last_number = int(last_role.code[2:])
            new_number = last_number + 1
        else:
            new_number = 3
        validated_data["code"] = f"VT{new_number:03d}"
        return super().create(validated_data)
```

**Option 2: Create a custom signal handler**
```python
@receiver(post_save, sender=CustomModel)
def generate_custom_code(sender, instance, created, **kwargs):
    if created and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        # Custom logic here
        instance.code = custom_code_generation_logic(instance)
        instance.save(update_fields=["code"])
```

## Code Examples Comparison

### Before Refactoring
```python
# 4 separate handlers, each ~25 lines
@receiver(post_save, sender=Branch)
def generate_branch_code(sender, instance, created, **kwargs):
    if created and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_model_code(instance)
        instance.save(update_fields=["code"])

@receiver(post_save, sender=Block)
def generate_block_code(sender, instance, created, **kwargs):
    if created and instance.code and instance.code.startswith(TEMP_CODE_PREFIX):
        instance.code = generate_model_code(instance)
        instance.save(update_fields=["code"])

# ... 2 more identical handlers
```

### After Refactoring
```python
# 1 generic handler for all models, ~15 lines total
_auto_code_handler = create_auto_code_signal_handler(TEMP_CODE_PREFIX)

@receiver(post_save, sender=Branch)
@receiver(post_save, sender=Block)
@receiver(post_save, sender=Department)
@receiver(post_save, sender=RecruitmentChannel)
def generate_model_code_on_save(sender, instance, created, **kwargs):
    _auto_code_handler(sender, instance, created, **kwargs)
```

## Testing

Comprehensive tests are provided in `tests/libs/test_code_generation.py`:

1. **Basic code generation tests** - Verify format for 1-3 digit IDs and 4+ digit IDs
2. **Signal handler tests** - Test the generic handler behavior:
   - Generates code for new instances with temporary code
   - Ignores existing instances
   - Ignores instances without temporary code
   - Handles instances without code attribute gracefully
   - Works with custom temporary prefix
3. **Registration tests** - Verify signal registration works correctly

## Migration Path

Existing models already using the old signal handlers will continue to work without changes. The refactoring is backward compatible:

1. Old signal handlers have been replaced with the generic handler
2. All existing tests should pass without modification
3. Model behavior remains identical

## Future Improvements

1. **Model Mixin:** Create a `AutoCodeMixin` that encapsulates the temporary code logic in save()
2. **Decorator:** Create a `@auto_code` class decorator to simplify model setup
3. **Configuration:** Allow CODE_PREFIX and format to be specified in settings
4. **Validation:** Add validation to ensure CODE_PREFIX is unique across all models

## References

- **Code Generation Module:** `libs/code_generation.py`
- **HRM Signals:** `apps/hrm/signals.py`
- **Example Models:** 
  - `apps/hrm/models/organization.py` (Branch, Block, Department)
  - `apps/hrm/models/recruitment_channel.py` (RecruitmentChannel)
- **Tests:** `tests/libs/test_code_generation.py`
- **Example Tests:**
  - `apps/hrm/tests/test_branch_auto_code.py`
  - `apps/hrm/tests/test_recruitment_channel_auto_code.py`
