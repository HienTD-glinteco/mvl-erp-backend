# Generated manually for mailtemplates

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailSendJob',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('template_slug', models.CharField(db_index=True, help_text='Slug of the template used for this job', max_length=100, verbose_name='Template slug')),
                ('subject', models.CharField(help_text='Subject line for the emails', max_length=500, verbose_name='Email subject')),
                ('sender', models.EmailField(help_text='From email address', max_length=254, verbose_name='Sender email')),
                ('total', models.PositiveIntegerField(default=0, help_text='Total number of recipients in this job', verbose_name='Total recipients')),
                ('sent_count', models.PositiveIntegerField(default=0, help_text='Number of successfully sent emails', verbose_name='Sent count')),
                ('failed_count', models.PositiveIntegerField(default=0, help_text='Number of failed email sends', verbose_name='Failed count')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], db_index=True, default='pending', help_text='Current status of the send job', max_length=20, verbose_name='Job status')),
                ('client_request_id', models.CharField(blank=True, db_index=True, help_text='Optional idempotency key provided by client', max_length=255, null=True, verbose_name='Client request ID')),
                ('started_at', models.DateTimeField(blank=True, help_text='When the job started processing', null=True, verbose_name='Started at')),
                ('finished_at', models.DateTimeField(blank=True, help_text='When the job finished processing', null=True, verbose_name='Finished at')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this send job', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_send_jobs', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
            ],
            options={
                'verbose_name': 'Email send job',
                'verbose_name_plural': 'Email send jobs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailSendRecipient',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(db_index=True, help_text='Email address of the recipient', max_length=254, verbose_name='Recipient email')),
                ('data', models.JSONField(help_text='Data used to render the template for this recipient', verbose_name='Template data')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')], db_index=True, default='pending', help_text='Current status of this email', max_length=20, verbose_name='Send status')),
                ('attempts', models.PositiveIntegerField(default=0, help_text='Number of send attempts', verbose_name='Attempt count')),
                ('last_error', models.TextField(blank=True, help_text='Error message from the last failed attempt', verbose_name='Last error')),
                ('message_id', models.CharField(blank=True, help_text='Provider message ID for tracking', max_length=255, verbose_name='Message ID')),
                ('sent_at', models.DateTimeField(blank=True, help_text='When the email was successfully sent', null=True, verbose_name='Sent at')),
                ('job', models.ForeignKey(help_text='The send job this recipient belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='mailtemplates.emailsendjob', verbose_name='Send job')),
            ],
            options={
                'verbose_name': 'Email send recipient',
                'verbose_name_plural': 'Email send recipients',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailsendjob',
            index=models.Index(fields=['-created_at'], name='mailtemplat_created_62c62e_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendjob',
            index=models.Index(fields=['status', '-created_at'], name='mailtemplat_status_24d393_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendjob',
            index=models.Index(fields=['created_by', '-created_at'], name='mailtemplat_created_76c21e_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendrecipient',
            index=models.Index(fields=['job', 'status'], name='mailtemplat_job_id_66e1a8_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendrecipient',
            index=models.Index(fields=['job', 'created_at'], name='mailtemplat_job_id_4b831e_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendrecipient',
            index=models.Index(fields=['email', '-created_at'], name='mailtemplat_email_e69d5d_idx'),
        ),
    ]
