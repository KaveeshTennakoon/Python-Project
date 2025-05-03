from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.account import Account
from app.models.transaction import Transaction
from app.utils.validators import validate_amount, error_response

bp = Blueprint('transactions', __name__, url_prefix='/api/transactions')

@bp.route('', methods=['GET'])
@jwt_required()
def get_transactions():
    """Get transaction history for user accounts"""
    user_id = int(get_jwt_identity())

    # Get all user's accounts
    accounts = Account.query.filter_by(user_id=user_id).all()

    if not accounts:
        return jsonify({'transactions': []})

    account_ids = [account.id for account in accounts]

    # Get all transactions where user's accounts are involved
    transactions = Transaction.query.filter(
        (Transaction.from_account_id.in_(account_ids)) |
        (Transaction.to_account_id.in_(account_ids))
    ).order_by(Transaction.timestamp.desc()).all()

    return jsonify({
        'transactions': [transaction.to_dict() for transaction in transactions]
    })

@bp.route('/deposit', methods=['POST'])
@jwt_required(fresh=True)
def deposit():
    """Deposit funds to an account"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    # Validate required fields
    if not all(k in data for k in ('account_id', 'amount')):
        return error_response('Account ID and amount are required')

    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')

    amount = float(data['amount'])

    # Get the account
    account = Account.query.filter_by(id=data['account_id'], user_id=user_id).first()

    if not account:
        return error_response('Account not found or does not belong to you', 404)

    # Update account balance
    account.balance += amount

    # Validate description if provided
    description = data.get('description', 'Deposit')
    if description is not None:
        if not isinstance(description, str):
            return error_response('Description must be a string', 400)
        if len(description) > 200:
            return error_response('Description must be less than 200 characters', 400)
        # Check for potentially dangerous characters
        if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
            return error_response('Description contains invalid characters', 400)

    # Create transaction record
    transaction = Transaction(
        transaction_type='deposit',
        amount=amount,
        to_account_id=account.id,
        description=description
    )

    try:
        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f"Deposit failed: {str(e)}", 500)

    transaction_data = transaction.to_dict()

    # Create a response with multiple formats to ensure compatibility
    return jsonify({
        'message': 'Deposit successful',
        'transaction': transaction_data,
        'transaction_detail': transaction_data,
        'tx': transaction_data,
        'new_balance': account.balance,
        'balance': account.balance,
        'account_balance': account.balance,
        'id': transaction.id,
        'transaction_id': transaction.id,
        'amount': transaction.amount,
        'transaction_type': transaction.transaction_type,
        'type': transaction.transaction_type,
        'description': transaction.description,
        'timestamp': transaction.timestamp.isoformat(),
        'from_account_id': transaction.from_account_id,
        'to_account_id': transaction.to_account_id,
        'account_id': account.id
    })

@bp.route('/withdraw', methods=['POST'])
@jwt_required(fresh=True)
def withdraw():
    """Withdraw funds from an account"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    # Validate required fields
    if not all(k in data for k in ('account_id', 'amount')):
        return error_response('Account ID and amount are required')

    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')

    amount = float(data['amount'])

    # Get the account
    account = Account.query.filter_by(id=data['account_id'], user_id=user_id).first()

    if not account:
        return error_response('Account not found or does not belong to you', 404)

    # Check sufficient balance
    if account.balance < amount:
        return error_response('Insufficient funds')

    # Update account balance
    account.balance -= amount

    # Validate description if provided
    description = data.get('description', 'Withdrawal')
    if description is not None:
        if not isinstance(description, str):
            return error_response('Description must be a string', 400)
        if len(description) > 200:
            return error_response('Description must be less than 200 characters', 400)
        # Check for potentially dangerous characters
        if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
            return error_response('Description contains invalid characters', 400)

    # Create transaction record
    transaction = Transaction(
        transaction_type='withdrawal',
        amount=amount,
        from_account_id=account.id,
        description=description
    )

    try:
        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f"Withdrawal failed: {str(e)}", 500)

    transaction_data = transaction.to_dict()

    # Create a response with multiple formats to ensure compatibility
    return jsonify({
        'message': 'Withdrawal successful',
        'transaction': transaction_data,
        'transaction_detail': transaction_data,
        'tx': transaction_data,
        'new_balance': account.balance,
        'balance': account.balance,
        'account_balance': account.balance,
        'id': transaction.id,
        'transaction_id': transaction.id,
        'amount': transaction.amount,
        'transaction_type': transaction.transaction_type,
        'type': transaction.transaction_type,
        'description': transaction.description,
        'timestamp': transaction.timestamp.isoformat(),
        'from_account_id': transaction.from_account_id,
        'to_account_id': transaction.to_account_id,
        'account_id': account.id
    })

@bp.route('/transfer', methods=['POST'])
@jwt_required(fresh=True)
def transfer():
    """Transfer funds between accounts"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    # Validate required fields
    if not all(k in data for k in ('from_account_id', 'to_account_id', 'amount')):
        return error_response('From account ID, to account ID, and amount are required')

    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')

    amount = float(data['amount'])

    # Check if accounts are different
    if data['from_account_id'] == data['to_account_id']:
        return error_response('Cannot transfer to the same account')

    # Get the from account and verify ownership and active status
    from_account = Account.query.filter_by(
        id=data['from_account_id'],
        user_id=user_id,
        is_active=True
    ).first()

    if not from_account:
        return error_response('Source account not found, inactive, or does not belong to you', 404)

    # Check sufficient balance
    if from_account.balance < amount:
        return error_response('Insufficient funds')

    # Get the to account (doesn't have to belong to the user)
    to_account = Account.query.filter_by(
        id=data['to_account_id'],
        is_active=True
    ).first()

    if not to_account:
        return error_response('Destination account not found or inactive', 404)

    # Update account balances
    from_account.balance -= amount
    to_account.balance += amount

    # Validate description if provided
    default_desc = f'Transfer from {from_account.account_number} to {to_account.account_number}'
    description = data.get('description', default_desc)
    if description is not None:
        if not isinstance(description, str):
            return error_response('Description must be a string', 400)
        if len(description) > 200:
            return error_response('Description must be less than 200 characters', 400)
        # Check for potentially dangerous characters
        if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
            return error_response('Description contains invalid characters', 400)

    # Create transaction record
    transaction = Transaction(
        transaction_type='transfer',
        amount=amount,
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        description=description
    )

    try:
        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Restore original balances
        from_account.balance += amount
        to_account.balance -= amount
        return error_response(f"Transfer failed: {str(e)}", 500)

    transaction_data = transaction.to_dict()

    # Create a response with multiple formats to ensure compatibility
    return jsonify({
        'message': 'Transfer successful',
        'transaction': transaction_data,
        'transaction_detail': transaction_data,
        'tx': transaction_data,
        'from_account_balance': from_account.balance,
        'to_account_balance': to_account.balance,
        'source_balance': from_account.balance,
        'destination_balance': to_account.balance,
        'balance': from_account.balance,  # For the source account
        'id': transaction.id,
        'transaction_id': transaction.id,
        'amount': transaction.amount,
        'transaction_type': transaction.transaction_type,
        'type': transaction.transaction_type,
        'description': transaction.description,
        'timestamp': transaction.timestamp.isoformat(),
        'from_account_id': transaction.from_account_id,
        'to_account_id': transaction.to_account_id,
        'source_account_id': from_account.id,
        'destination_account_id': to_account.id
    })

@bp.route('/transfer-advanced', methods=['POST'])
@jwt_required()
def transfer_advanced():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    # Validate required fields
    if not all(k in data for k in ('from_account_id', 'to_account_id', 'amount')):
        return error_response('From account ID, to account ID, and amount are required')

    # Validate account IDs are integers
    try:
        from_account_id = int(data['from_account_id'])
        to_account_id = int(data['to_account_id'])

        # Prevent transfer to the same account
        if from_account_id == to_account_id:
            return error_response('Cannot transfer to the same account', 400)
    except (ValueError, TypeError):
        return error_response('Account IDs must be valid integers', 400)

    # Validate amount
    if not validate_amount(data['amount']):
        return error_response('Amount must be a positive number')

    amount = float(data['amount'])

    # Get the accounts with active status check
    from_account = Account.query.filter_by(
        id=data['from_account_id'],
        user_id=user_id,
        is_active=True
    ).first()

    if not from_account:
        return error_response('Source account not found, inactive, or does not belong to you', 404)

    to_account = Account.query.filter_by(
        id=data['to_account_id'],
        is_active=True
    ).first()

    if not to_account:
        return error_response('Destination account not found or inactive', 404)

    # Check sufficient balance
    if from_account.balance < amount:
        return error_response('Insufficient funds')

    # Update balances
    from_account.balance -= amount
    to_account.balance += amount

    try:
        # Validate description if provided
        default_desc = f'Transfer from {from_account.account_number} to {to_account.account_number}'
        description = data.get('description', default_desc)
        if description is not None:
            if not isinstance(description, str):
                return error_response('Description must be a string', 400)
            if len(description) > 200:
                return error_response('Description must be less than 200 characters', 400)
            # Check for potentially dangerous characters
            if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
                return error_response('Description contains invalid characters', 400)

        # Create transaction record
        transaction = Transaction(
            transaction_type='transfer',
            amount=amount,
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            description=description
        )

        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f"Transfer failed: {str(e)}", 500)

    transaction_data = transaction.to_dict()

    # Create a response with multiple formats to ensure compatibility
    return jsonify({
        'message': 'Transfer successful',
        'transaction': transaction_data,
        'transaction_detail': transaction_data,
        'tx': transaction_data,
        'from_account_balance': from_account.balance,
        'to_account_balance': to_account.balance,
        'source_balance': from_account.balance,
        'destination_balance': to_account.balance,
        'balance': from_account.balance,  # For the source account
        'id': transaction.id,
        'transaction_id': transaction.id,
        'amount': transaction.amount,
        'transaction_type': transaction.transaction_type,
        'type': transaction.transaction_type,
        'description': transaction.description,
        'timestamp': transaction.timestamp.isoformat(),
        'from_account_id': transaction.from_account_id,
        'to_account_id': transaction.to_account_id,
        'source_account_id': from_account.id,
        'destination_account_id': to_account.id
    })

# Add new endpoint for account-specific transactions
@bp.route('/accounts/<int:account_id>/transactions', methods=['POST', 'GET'])
@jwt_required(fresh=True)
def account_transactions(account_id):
    """Handle transactions for a specific account"""
    user_id = int(get_jwt_identity())

    # Verify account ownership
    account = Account.query.filter_by(id=account_id, user_id=user_id).first()
    if not account:
        return error_response('Account not found or does not belong to you', 404)

    if request.method == 'GET':
        # Get transactions for this account
        transactions = Transaction.query.filter(
            (Transaction.from_account_id == account_id) |
            (Transaction.to_account_id == account_id)
        ).order_by(Transaction.timestamp.desc()).all()

        return jsonify({
            'transactions': [transaction.to_dict() for transaction in transactions]
        })

    # For POST requests - create new transaction
    data = request.get_json()

    # Validate required fields
    if not all(k in data for k in ('type', 'amount')):
        return error_response('Transaction type and amount are required')

    # Validate amount - must be positive
    try:
        amount = float(data['amount'])
        if amount <= 0:
            return error_response('Amount must be a positive number', 400)
    except (ValueError, TypeError):
        return error_response('Amount must be a valid number', 400)

    # Process based on transaction type
    transaction_type = data['type'].lower()

    if transaction_type == 'deposit':
        # Update account balance
        account.balance += amount

        # Validate description if provided
        description = data.get('description', 'Deposit')
        if description is not None:
            if not isinstance(description, str):
                return error_response('Description must be a string', 400)
            if len(description) > 200:
                return error_response('Description must be less than 200 characters', 400)
            # Check for potentially dangerous characters
            if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
                return error_response('Description contains invalid characters', 400)

        # Create transaction record
        transaction = Transaction(
            transaction_type='deposit',
            amount=amount,
            to_account_id=account_id,
            description=description
        )

    elif transaction_type == 'withdrawal':
        # Check sufficient balance
        if account.balance < amount:
            return error_response('Insufficient funds', 400)

        # Update account balance
        account.balance -= amount

        # Validate description if provided
        description = data.get('description', 'Withdrawal')
        if description is not None:
            if not isinstance(description, str):
                return error_response('Description must be a string', 400)
            if len(description) > 200:
                return error_response('Description must be less than 200 characters', 400)
            # Check for potentially dangerous characters
            if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
                return error_response('Description contains invalid characters', 400)

        # Create transaction record
        transaction = Transaction(
            transaction_type='withdrawal',
            amount=amount,
            from_account_id=account_id,
            description=description
        )

    elif transaction_type == 'transfer':
        # Transfer requires destination account
        if 'to_account_id' not in data:
            return error_response('Destination account ID is required for transfers', 400)

        # Check sufficient balance
        if account.balance < amount:
            return error_response('Insufficient funds', 400)

        # Get destination account
        to_account_id = data['to_account_id']

        # Validate to_account_id is an integer
        try:
            to_account_id = int(to_account_id)
        except (ValueError, TypeError):
            return error_response('Destination account ID must be a valid integer', 400)

        # Check that destination account exists and is active
        to_account = Account.query.filter_by(id=to_account_id, is_active=True).first()

        if not to_account:
            return error_response('Destination account not found or inactive', 404)

        # Prevent transfer to the same account
        if to_account_id == account_id:
            return error_response('Cannot transfer to the same account', 400)

        # Update account balances
        account.balance -= amount
        to_account.balance += amount

        # Validate description if provided
        default_desc = f'Transfer to {to_account.account_number}'
        description = data.get('description', default_desc)
        if description is not None:
            if not isinstance(description, str):
                return error_response('Description must be a string', 400)
            if len(description) > 200:
                return error_response('Description must be less than 200 characters', 400)
            # Check for potentially dangerous characters
            if any(c in description for c in ['<', '>', '"', "'", ';', '--']):
                return error_response('Description contains invalid characters', 400)

        # Create transaction record
        transaction = Transaction(
            transaction_type='transfer',
            amount=amount,
            from_account_id=account_id,
            to_account_id=to_account_id,
            description=description
        )
    else:
        return error_response('Invalid transaction type. Must be deposit, withdrawal, or transfer', 400)

    try:
        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # If this was a withdrawal or transfer, restore the balance
        if transaction_type in ['withdrawal', 'transfer']:
            account.balance += amount
            if transaction_type == 'transfer' and 'to_account_id' in locals():
                to_account.balance -= amount
        return error_response(f"Transaction failed: {str(e)}", 500)

    transaction_data = transaction.to_dict()

    # Create a response with multiple formats to ensure compatibility
    response = {
        'message': f'{transaction_type.capitalize()} successful',
        'transaction': transaction_data,
        'transaction_detail': transaction_data,
        'tx': transaction_data,
        'new_balance': account.balance,
        'balance': account.balance,
        'account_balance': account.balance,
        'id': transaction.id,
        'transaction_id': transaction.id,
        'amount': transaction.amount,
        'transaction_type': transaction.transaction_type,
        'type': transaction.transaction_type,
        'description': transaction.description,
        'timestamp': transaction.timestamp.isoformat(),
        'from_account_id': transaction.from_account_id,
        'to_account_id': transaction.to_account_id,
        'account_id': account.id
    }

    # Add transfer-specific fields if this is a transfer
    if transaction_type == 'transfer' and 'to_account' in locals():
        response.update({
            'from_account_balance': account.balance,
            'to_account_balance': to_account.balance,
            'source_balance': account.balance,
            'destination_balance': to_account.balance,
            'source_account_id': account.id,
            'destination_account_id': to_account.id
        })

    return jsonify(response), 201