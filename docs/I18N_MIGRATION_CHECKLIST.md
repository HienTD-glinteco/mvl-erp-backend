# I18n Migration Checklist

## For Reviewers

Before merging this PR, please verify:

- [ ] Code review completed
- [ ] All English strings are grammatically correct and clear
- [ ] Vietnamese translations in `locale/vi/LC_MESSAGES/django.po` are accurate
- [ ] No hardcoded Vietnamese strings remain (except in migrations - those are historical)
- [ ] Pre-commit hooks pass

## For Deployment

### Step 1: Merge and Pull
```bash
git checkout master
git pull origin master
```

### Step 2: Install/Update Dependencies
Ensure all dependencies are up to date (no new dependencies were added for i18n as Django includes it).

### Step 3: Compile Translation Files
```bash
python manage.py compilemessages
```

This will create `locale/vi/LC_MESSAGES/django.mo` which is the compiled binary translation file.

**Important**: The `.mo` files should be committed to the repository for production deployments, or generated during the deployment process.

### Step 4: Run Tests
```bash
pytest
# or
make test
```

### Step 5: Verify in Development
```bash
python manage.py runserver
```

Test the following:
1. Login flow - check all error messages
2. Password change flow
3. Password reset flow
4. Email templates (check email sent)
5. Admin interface (optional)

### Step 6: Database Migrations
**No database migrations are required** - this change only affects:
- How text is displayed
- Translation files
- Template rendering

Model field changes (verbose_name) don't affect database schema.

## For Developers

### Adding New Translatable Strings

When adding new features:

1. **Write strings in English**
   ```python
   from django.utils.translation import gettext as _
   
   error_message = _("Invalid email address")
   ```

2. **Update translations**
   ```bash
   python manage.py makemessages -l vi --no-obsolete
   ```

3. **Edit the .po file**
   Open `locale/vi/LC_MESSAGES/django.po` and add Vietnamese translation:
   ```
   msgid "Invalid email address"
   msgstr "Địa chỉ email không hợp lệ"
   ```

4. **Compile (for testing)**
   ```bash
   python manage.py compilemessages
   ```

5. **Commit both .po and .mo files**
   ```bash
   git add locale/
   git commit -m "Add translation for new feature"
   ```

### Pre-commit Hook
The pre-commit hook automatically runs `makemessages` when you commit changes to .py or .html files. This ensures translations are always up to date.

## Common Issues and Solutions

### Issue 1: Translations not showing
**Solution**: Run `compilemessages` to generate .mo files

### Issue 2: New strings not translated
**Solution**: 
1. Run `makemessages`
2. Add translation in .po file
3. Run `compilemessages`

### Issue 3: Fuzzy translations
If makemessages marks a translation as "fuzzy", it means the English string changed slightly:
1. Review the translation
2. Update if needed
3. Remove the `#, fuzzy` comment
4. Compile messages

### Issue 4: Pre-commit hook fails
**Solution**: 
```bash
# Run manually to see errors
python manage.py makemessages -l vi --no-obsolete

# Fix issues, then commit
git add locale/
git commit
```

## Rollback Plan

If issues arise after deployment:

1. **Quick fix**: Revert the PR
   ```bash
   git revert <commit-hash>
   git push origin master
   ```

2. **Specific file issues**: Revert specific files if only certain areas have problems

3. **Translation fixes**: If only translations are wrong, just update the .po file and recompile:
   ```bash
   # Edit locale/vi/LC_MESSAGES/django.po
   python manage.py compilemessages
   git add locale/vi/LC_MESSAGES/django.mo
   git commit -m "Fix translation errors"
   ```

## Performance Impact

**Expected**: None or negligible
- Django caches translations in memory
- Translation lookup is very fast
- .mo files are binary and optimized for speed

## Browser/Client Impact

**Expected**: None
- This is a server-side change only
- API responses remain the same (JSON structure unchanged)
- Only the text content of messages changes from Vietnamese to Vietnamese (via translation)

## Monitoring

After deployment, monitor:
- Application logs for any UnicodeDecodeError or translation errors
- User feedback on displayed text
- Email delivery (check templates render correctly)

## Questions?

Contact the development team or refer to:
- Django i18n documentation: https://docs.djangoproject.com/en/5.1/topics/i18n/
- Project Copilot instructions: `.github/copilot-instructions.md`
