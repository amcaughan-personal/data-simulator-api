resource "aws_s3_bucket" "deliberately_insecure" {
  bucket = "blocking-test-do-not-merge"
}
