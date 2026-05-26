import os
import boto3
import frappe
from frappe.utils.file_manager import save_file_on_filesystem, delete_file_from_filesystem

def get_s3_client(s3_config):
	return boto3.client(
		"s3",
		aws_access_key_id=s3_config.get("s3_access_key"),
		aws_secret_access_key=s3_config.get("s3_secret_key"),
		endpoint_url=s3_config.get("s3_endpoint_url"),
		config=boto3.session.Config(signature_version="s3v4")
	)

def get_s3_config():
	# Retrieve configuration dynamically from the active site's site_config.json
	config = frappe.conf
	if config.get("s3_bucket") and config.get("s3_access_key") and config.get("s3_secret_key"):
		return {
			"s3_access_key": config.get("s3_access_key"),
			"s3_secret_key": config.get("s3_secret_key"),
			"s3_bucket": config.get("s3_bucket"),
			"s3_endpoint_url": config.get("s3_endpoint_url"),
			"s3_public_domain": config.get("s3_public_domain")  # Custom domain or public R2 CDN url
		}
	return None

def get_s3_prefix():
	"""
	Retrieves the folder prefix for S3/R2.
	Priority:
	1. Explicit 's3_prefix' in site_config.json
	2. Site's subdomain only (e.g. 'development' from 'development.localhost')
	"""
	custom_prefix = frappe.conf.get("s3_prefix")
	if custom_prefix:
		return custom_prefix.strip("/")
	
	site_name = frappe.local.site
	return site_name.split(".")[0]

def write_file_to_r2(file_doc, content=None, content_type=None, is_private=0):
	# Detect if called as a hook (File document) or manually (filename string)
	is_hook = not isinstance(file_doc, str) and hasattr(file_doc, "file_name")
	
	if is_hook:
		doc = file_doc
		fname = doc.file_name
		content = doc.get_content()
		content_type = doc.content_type
		is_private = doc.is_private
	else:
		fname = file_doc

	s3_config = get_s3_config()
	if not s3_config:
		# Fall back to native local file storage if not configured in site_config.json
		if is_hook:
			return file_doc.save_file_on_filesystem()
		return save_file_on_filesystem(fname, content, content_type, is_private)

	bucket_name = s3_config.get("s3_bucket")
	s3_prefix = get_s3_prefix()
	prefix = "private" if is_private else "public"
	s3_key = f"{s3_prefix}/{prefix}/{fname}"

	if isinstance(content, str):
		content = content.encode("utf-8")

	try:
		s3 = get_s3_client(s3_config)
		s3.put_object(
			Bucket=bucket_name,
			Key=s3_key,
			Body=content,
			ContentType=content_type or "application/octet-stream"
		)
		
		# Generate file URL. Use custom public CDN domain if available, otherwise R2 endpoint
		public_domain = s3_config.get("s3_public_domain")
		if public_domain:
			if not public_domain.startswith(("http://", "https://", "//")):
				public_domain = "https://" + public_domain
			file_url = f"{public_domain.rstrip('/')}/{s3_key}"
		else:
			endpoint = s3_config.get("s3_endpoint_url").rstrip("/")
			if not endpoint.startswith(("http://", "https://", "//")):
				endpoint = "https://" + endpoint
			file_url = f"{endpoint}/{bucket_name}/{s3_key}"
			
		if is_hook:
			file_doc.file_url = file_url
			
		return {"file_name": fname, "file_url": file_url}
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title="R2 File Upload Error")
		# Safe fallback to local disk storage if upload fails
		if is_hook:
			return file_doc.save_file_on_filesystem()
		return save_file_on_filesystem(fname, content, content_type, is_private)

def delete_file_from_r2(doc, only_thumbnail=False):
	s3_config = get_s3_config()
	if not s3_config:
		# Fall back to local filesystem deletion
		return delete_file_from_filesystem(doc, only_thumbnail)

	def delete_url(url):
		if not url:
			return
		bucket_name = s3_config.get("s3_bucket")
		
		# Parse the key out of the url
		s3_prefix = get_s3_prefix()
		site_name = frappe.local.site
		key = ""
		if f"{s3_prefix}/public/" in url:
			key = f"{s3_prefix}/public/" + url.split(f"{s3_prefix}/public/", 1)[1]
		elif f"{s3_prefix}/private/" in url:
			key = f"{s3_prefix}/private/" + url.split(f"{s3_prefix}/private/", 1)[1]
		elif f"{site_name}/public/" in url:
			key = f"{site_name}/public/" + url.split(f"{site_name}/public/", 1)[1]
		elif f"{site_name}/private/" in url:
			key = f"{site_name}/private/" + url.split(f"{site_name}/private/", 1)[1]
		elif "public/" in url:
			key = "public/" + url.split("public/", 1)[1]
		elif "private/" in url:
			key = "private/" + url.split("private/", 1)[1]

		if key:
			try:
				s3 = get_s3_client(s3_config)
				s3.delete_object(Bucket=bucket_name, Key=key)
			except Exception as e:
				frappe.log_error(message=frappe.get_traceback(), title="R2 File Deletion Error")

	if only_thumbnail:
		delete_url(doc.thumbnail_url)
	else:
		delete_url(doc.file_url)
		delete_url(doc.thumbnail_url)
