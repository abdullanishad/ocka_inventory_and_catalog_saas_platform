# orders/services.py
import razorpay
from django.conf import settings
from .models import Order

def release_payment_to_wholesaler(order: Order):
    """
    Handles the logic for creating a Razorpay Linked Account and transferring funds.
    Returns (True, "Success message") or (False, "Error message").
    """
    # 1. Check if the order is ready for payout
    if order.status != Order.Status.SHIPPED:
        return (False, f"Order {order.number} is not in SHIPPED status.")

    wholesaler_profile = order.wholesaler.users.first().profile
    if not (wholesaler_profile.bank_account_number and wholesaler_profile.bank_ifsc_code):
        return (False, f"Wholesaler for order {order.number} has incomplete bank details.")

    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        # NOTE: In a real app, you would create and store the Linked Account ID once
        # for each wholesaler to avoid creating it every time. This is a simplified example.
        linked_account = client.account.create({
            "type": "standard",
            "email": order.wholesaler.users.first().email,
            "phone": wholesaler_profile.phone,
            "legal_business_name": order.wholesaler.name,
            "contact_name": wholesaler_profile.bank_account_holder_name,
            "bank_account": {
                "ifsc_code": wholesaler_profile.bank_ifsc_code,
                "account_number": wholesaler_profile.bank_account_number,
                "name": wholesaler_profile.bank_account_holder_name
            }
        })
        linked_account_id = linked_account['id']

        # 2. Calculate amount to transfer (e.g., after a 5% commission)
        commission_rate = 0.05
        transfer_amount = int(order.total_value * (1 - commission_rate) * 100) # Amount in paise

        # 3. Initiate the Transfer from the captured payment
        transfer = client.payment.transfer(order.razorpay_payment_id, {
            "transfers": [
                {
                    "account": linked_account_id,
                    "amount": transfer_amount,
                    "currency": "INR"
                }
            ]
        })

        # 4. Update Order Status
        order.status = Order.Status.COMPLETED
        order.save()
        
        return (True, f"Successfully released payment for order {order.number}.")

    except Exception as e:
        return (False, f"Error processing payment for {order.number}: {str(e)}")