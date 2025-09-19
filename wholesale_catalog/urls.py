from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from catalog import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),  # make this your landing page
    path("catalog/", include("catalog.urls")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("orders/", include("orders.urls", namespace="orders")),
    path("r2-live-debug-9f3b8a/", r2_debug),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# TEMPORARY: r2 debug endpoint — remove after debugging
from django.urls import path
from django.http import HttpResponse
import traceback

def r2_debug(request):
    out = []
    try:
        # show settings info
        from django.conf import settings
        out.append(f"DEBUG={settings.DEBUG}")
        out.append(f"DEFAULT_FILE_STORAGE={getattr(settings,'DEFAULT_FILE_STORAGE',None)}")
        out.append(f"AWS_S3_ENDPOINT_URL={getattr(settings,'AWS_S3_ENDPOINT_URL',None)}")
        out.append(f"AWS_STORAGE_BUCKET_NAME={getattr(settings,'AWS_STORAGE_BUCKET_NAME',None)}")

        # storage checks
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        out.append(f"default_storage_class={default_storage.__class__}")

        # try to save a small test file
        name = default_storage.save("debug_test/r2_live_check.txt", ContentFile(b"r2 live check"))
        out.append(f"saved_name={name}")
        out.append(f"exists_via_default_storage={default_storage.exists(name)}")
        try:
            url = default_storage.url(name)
            out.append(f"public_url={url}")
        except Exception as e:
            out.append("url_error:" + str(e))

        # use boto3 with same env to list objects in bucket and buckets list
        import os, boto3, botocore
        endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
        key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME")
        out.append(f"env_key_present={bool(key)} env_secret_present={bool(secret)} endpoint={endpoint} bucket={bucket}")

        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=key,
                aws_secret_access_key=secret,
                region_name=os.environ.get("AWS_S3_REGION_NAME","auto"),
            )
            # list buckets
            try:
                bs = s3.list_buckets()
                out.append("list_buckets_ok: " + ", ".join([b['Name'] for b in bs.get('Buckets', [])][:20]))
            except botocore.exceptions.ClientError as e:
                out.append("list_buckets_error: " + str(e))

            # list objects under debug_test/
            try:
                resp = s3.list_objects_v2(Bucket=bucket, Prefix="debug_test/")
                out.append("list_objects_KeyCount=" + str(resp.get("KeyCount", 0)))
                for obj in resp.get("Contents", []):
                    out.append("OBJ: " + obj["Key"] + " size=" + str(obj["Size"]))
            except botocore.exceptions.ClientError as e:
                out.append("list_objects_error: " + str(e))
        except Exception as e:
            out.append("boto3_client_error: " + traceback.format_exc())

    except Exception:
        out.append("outer_exception: " + traceback.format_exc())

    return HttpResponse("\n".join(out), content_type="text/plain")
